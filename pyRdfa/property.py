# -*- coding: utf-8 -*-
"""
Implementation of the C{@property} value handling.

RDFa 1.0 and RDFa 1.1 are fairly different. RDFa 1.0 generates only literals, see
U{RDFa Task Force's wiki page<http://www.w3.org/2006/07/SWD/wiki/RDFa/LiteralObject>} for the details.
On the other hand, RDFa 1.1, beyond literals, can also generate URI references. Hence the duplicate method in the L{ProcessProperty} class, one for RDFa 1.0 and the other for RDFa 1.1.

@summary: RDFa Literal generation
@requires: U{RDFLib package<http://rdflib.net>}
@organization: U{World Wide Web Consortium<http://www.w3.org>}
@author: U{Ivan Herman<a href="http://www.w3.org/People/Ivan/">}
@license: This software is available for use under the
U{W3C® SOFTWARE NOTICE AND LICENSE<href="http://www.w3.org/Consortium/Legal/2002/copyright-software-20021231">}
"""

"""
$Id: property.py,v 1.13 2013-07-26 12:35:51 ivan Exp $
$Date: 2013-07-26 12:35:51 $
"""

import re, sys

import rdflib
from rdflib	import BNode
from rdflib	import Literal, URIRef, Namespace
if rdflib.__version__ >= "3.0.0" :
	from rdflib	     import RDF as ns_rdf
	from rdflib.term import XSDToPython
else :
	from rdflib.RDF	    import RDFNS as ns_rdf
	from rdflib.Literal import XSDToPython

from .	         import IncorrectBlankNodeUsage, IncorrectLiteral, err_no_blank_node, ns_xsd 
from .utils      import has_one_of_attributes, return_XML
from .host.html5 import handled_time_types

XMLLiteral  = ns_rdf["XMLLiteral"]
HTMLLiteral = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#HTML") 

class ProcessProperty :
	"""Generate the value for C{@property} taking into account datatype, etc.
	Note: this class is created only if the C{@property} is indeed present, no need to check. 
	
	@ivar node: DOM element node
	@ivar graph: the (RDF) graph to add the properies to
	@ivar subject: the RDFLib URIRef serving as a subject for the generated triples
	@ivar state: the current state to be used for the CURIE-s
	@type state: L{state.ExecutionContext}
	@ivar typed_resource: Typically the bnode generated by a @typeof
	"""
	def __init__(self, node, graph, subject, state, typed_resource = None) :
		"""
		@param node: DOM element node
		@param graph: the (RDF) graph to add the properies to
		@param subject: the RDFLib URIRef serving as a subject for the generated triples
		@param state: the current state to be used for the CURIE-s
		@param state: L{state.ExecutionContext}
		@param typed_resource: Typically the bnode generated by a @typeof; in RDFa 1.1, that becomes the object for C{@property}
		"""
		self.node           = node
		self.graph          = graph
		self.subject        = subject
		self.state          = state
		self.typed_resource = typed_resource
		
	def generate(self) :
		"""
		Common entry point for the RDFa 1.0 and RDFa 1.1 versions; bifurcates based on the RDFa version, as retrieved from the state object.
		"""
		if self.state.rdfa_version >= "1.1" :
			self.generate_1_1()
		else :
			self.generate_1_0()
	
	def generate_1_1(self) :
		"""Generate the property object, 1.1 version"""
				
		#########################################################################		
		# See if the target is _not_ a literal
		irirefs      = ("resource", "href", "src")
		noiri        = ("content", "datatype", "rel", "rev")
		notypediri   = ("content", "datatype", "rel", "rev", "about", "about_pruned")
		if has_one_of_attributes(self.node, irirefs) and not has_one_of_attributes(self.node, noiri) :
			# @href/@resource/@src takes the lead here...
			object = self.state.getResource(irirefs)
		elif self.node.hasAttribute("typeof") and not has_one_of_attributes(self.node, notypediri) and self.typed_resource != None :
				# a @typeof creates a special branch in case the typed resource was set during parsing
				object = self.typed_resource
		else :
			# We have to generate a literal
			
			# Get, if exists, the value of @datatype
			datatype = ''
			dtset    = False
			if self.node.hasAttribute("datatype") :
				dtset = True
				dt = self.node.getAttribute("datatype")
				if dt != "" :
					datatype = self.state.getURI("datatype")
		
			# Supress lange is set in case some elements explicitly want to supress the effect of language
			# There were discussions, for example, that the <time> element should do so. Although,
			# after all, this was reversed, the functionality is kept in the code in case another
			# element might need it...
			if self.state.lang != None and self.state.supress_lang == False :
				lang = self.state.lang
			else :
				lang = ''
	
			# The simple case: separate @content attribute
			if self.node.hasAttribute("content") :
				val = self.node.getAttribute("content")
				# Handling the automatic uri conversion case
				if dtset == False :
					object = Literal(val, lang=lang)
				else :
					object = self._create_Literal(val, datatype=datatype, lang=lang)
				# The value of datatype has been set, and the keyword paramaters take care of the rest
			else :
				# see if there *is* a datatype (even if it is empty!)
				if dtset :
					if datatype == XMLLiteral :
						litval = self._get_XML_literal(self.node)
						object = Literal(litval,datatype=XMLLiteral)
					elif datatype == HTMLLiteral :
						# I am not sure why this hack is necessary, but otherwise an encoding error occurs
						# In Python3 all this should become moot, due to the unicode everywhere approach...
						if sys.version_info[0] >= 3 :
							object = Literal(self._get_HTML_literal(self.node), datatype=HTMLLiteral)
						else :
							litval = self._get_HTML_literal(self.node)
							o = Literal(litval, datatype=XMLLiteral)
							object = Literal(o, datatype=HTMLLiteral)					
					else :
						object = self._create_Literal(self._get_literal(self.node), datatype=datatype, lang=lang)
				else :
					object = self._create_Literal(self._get_literal(self.node), lang=lang)
	
		if object != None :
			for prop in self.state.getURI("property") :
				if not isinstance(prop, BNode) :
					if self.node.hasAttribute("inlist") :
						self.state.add_to_list_mapping(prop, object)
					else :			
						self.graph.add( (self.subject, prop, object) )
				else :
					self.state.options.add_warning(err_no_blank_node % "property", warning_type=IncorrectBlankNodeUsage, node=self.node.nodeName)
	
		# return

	def generate_1_0(self) :
		"""Generate the property object, 1.0 version"""
				
		#########################################################################		
		# We have to generate a literal indeed.
		# Get, if exists, the value of @datatype
		datatype = ''
		dtset    = False
		if self.node.hasAttribute("datatype") :
			dtset = True
			dt = self.node.getAttribute("datatype")
			if dt != "" :
				datatype = self.state.getURI("datatype")
	
		if self.state.lang != None :
			lang = self.state.lang
		else :
			lang = ''

		# The simple case: separate @content attribute
		if self.node.hasAttribute("content") :
			val = self.node.getAttribute("content")
			# Handling the automatic uri conversion case
			if dtset == False :
				object = Literal(val, lang=lang)
			else :
				object = self._create_Literal(val, datatype=datatype, lang=lang)
			# The value of datatype has been set, and the keyword paramaters take care of the rest
		else :
			# see if there *is* a datatype (even if it is empty!)
			if dtset :
				# yep. The Literal content is the pure text part of the current element:
				# We have to check whether the specified datatype is, in fact, an
				# explicit XML Literal
				if datatype == XMLLiteral :
					litval = self._get_XML_literal(self.node)
					object = Literal(litval,datatype=XMLLiteral)
				elif datatype == HTMLLiteral :
					# I am not sure why this hack is necessary, but otherwise an encoding error occurs
					# In Python3 all this should become moot, due to the unicode everywhere approach...
					if sys.version_info[0] >= 3 :
						object = Literal(self._get_HTML_literal(self.node), datatype=HTMLLiteral)
					else :
						litval = self._get_HTML_literal(self.node)
						o = Literal(litval, datatype=XMLLiteral)	
						object = Literal(o, datatype=HTMLLiteral)					
				else :
					object = self._create_Literal(self._get_literal(self.node), datatype=datatype, lang=lang)
			else :
				# no controlling @datatype. We have to see if there is markup in the contained
				# element
				if True in [ n.nodeType == self.node.ELEMENT_NODE for n in self.node.childNodes ] :
					# yep, and XML Literal should be generated
					object = self._create_Literal(self._get_XML_literal(self.node), datatype=XMLLiteral)
				else :
					# At this point, there might be entities in the string that are returned as real characters by the dom
					# implementation. That should be turned back
					object = self._create_Literal(self._get_literal(self.node), lang=lang)
	
		for prop in self.state.getURI("property") :
			if not isinstance(prop,BNode) :
				self.graph.add( (self.subject,prop,object) )
			else :
				self.state.options.add_warning(err_no_blank_node % "property", warning_type=IncorrectBlankNodeUsage, node=self.node.nodeName)
	
		# return
	
	######################################################################################################################################
	
	
	def _putBackEntities(self, str) :
		"""Put 'back' entities for the '&','<', and '>' characters, to produce a proper XML string.
		Used by the XML Literal extraction.
		@param str: string to be converted
		@return: string with entities
		@rtype: string
		"""
		return str.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
		
	def _get_literal(self, Pnode):
		"""
		Get (recursively) the full text from a DOM Node.
	
		@param Pnode: DOM Node
		@return: string
		"""
		rc = ""
		for node in Pnode.childNodes:
			if node.nodeType == node.TEXT_NODE:
				rc = rc + node.data
			elif node.nodeType == node.ELEMENT_NODE :
				rc = rc + self._get_literal(node)
	
		# The decision of the group in February 2008 is not to normalize the result by default.
		# This is reflected in the default value of the option		
		
		if self.state.options.space_preserve :
			return rc
		else :
			return re.sub(r'(\r| |\n|\t)+'," ",rc).strip()
	# end getLiteral
	
	def _get_XML_literal(self, Pnode) :
		"""
		Get (recursively) the XML Literal content of a DOM Node. 
	
		@param Pnode: DOM Node
		@return: string
		"""	
		rc = ""		
		for node in Pnode.childNodes:
			if node.nodeType == node.TEXT_NODE:
				rc = rc + self._putBackEntities(node.data)
			elif node.nodeType == node.ELEMENT_NODE :
				rc = rc + return_XML(self.state, node, base = False)
		return rc
	# end getXMLLiteral

	def _get_HTML_literal(self, Pnode) :
		"""
		Get (recursively) the XML Literal content of a DOM Node. 
	
		@param Pnode: DOM Node
		@return: string
		"""	
		rc = ""		
		for node in Pnode.childNodes:
			if node.nodeType == node.TEXT_NODE:
				rc = rc + self._putBackEntities(node.data)
			elif node.nodeType == node.ELEMENT_NODE :
				rc = rc + return_XML(self.state, node, base = False, xmlns = False )
		return rc
	# end getHTMLLLiteral
	
	def _create_Literal(self, val, datatype = '', lang = '') :
		"""
		Create a literal, taking into account the datatype and language.
		@return: Literal
		"""
		if datatype == None or datatype == '' :
			return Literal(val, lang=lang)
		#elif datatype == ns_xsd["string"] :
		#	return Literal(val)
		else :
			# This is a bit convoluted... the default setup of rdflib does not gracefully react if the
			# datatype cannot properly be converted to Python. I have to copy and reuse some of the
			# rdflib code to get this working...
			# To make things worse: rdlib 3.1.0 does not handle the various xsd date types properly, ie,
			# the conversion function below will generate errors. Ie, the check should be skipped for those
			if ("%s" % datatype) in handled_time_types and rdflib.__version__ < "3.2.0" :
				convFunc = False
			else :
				convFunc = XSDToPython.get(datatype, None)
			if convFunc :
				try :
					pv = convFunc(val)
					# If we got there the literal value and its datatype match
				except :
					self.state.options.add_warning("Incompatible value (%s) and datatype (%s) in Literal definition." % (val, datatype), warning_type=IncorrectLiteral, node=self.node.nodeName)
			return Literal(val, datatype=datatype)
