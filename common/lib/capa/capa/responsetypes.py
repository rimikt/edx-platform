#
# File:   courseware/capa/responsetypes.py
#
'''
Problem response evaluation.  Handles checking of student responses, of a variety of types.

Used by capa_problem.py
'''

# standard library imports
import abc
import cgi
import hashlib
import inspect
import json
import logging
import numbers
import numpy
import os
import random
import re
import requests
import subprocess
import traceback
import xml.sax.saxutils as saxutils

from collections import namedtuple
from shapely.geometry import Point, MultiPoint

# specific library imports
from calc import evaluator, UndefinedVariable
from correctmap import CorrectMap
from datetime import datetime
from util import *
from lxml import etree
from lxml.html.soupparser import fromstring as fromstring_bs	 # uses Beautiful Soup!!! FIXME?
import xqueue_interface

log = logging.getLogger('mitx.' + __name__)


#-----------------------------------------------------------------------------
# Exceptions


class LoncapaProblemError(Exception):
    '''
    Error in specification of a problem
    '''
    pass


class ResponseError(Exception):
    '''
    Error for failure in processing a response
    '''
    pass


class StudentInputError(Exception):
    pass

#-----------------------------------------------------------------------------
#
# Main base class for CAPA responsetypes


class LoncapaResponse(object):
    """
    Base class for CAPA responsetypes.  Each response type (ie a capa question,
    which is part of a capa problem) is represented as a subclass,
    which should provide the following methods:

      - get_score           : evaluate the given student answers, and return a CorrectMap
      - get_answers         : provide a dict of the expected answers for this problem

    Each subclass must also define the following attributes:

      - response_tag         : xhtml tag identifying this response (used in auto-registering)

    In addition, these methods are optional:

      - setup_response : find and note the answer input field IDs for the response; called
                         by __init__

      - check_hint_condition : check to see if the student's answers satisfy a particular
                               condition for a hint to be displayed

      - render_html          : render this Response as HTML (must return XHTML-compliant string)
      - __unicode__          : unicode representation of this Response

    Each response type may also specify the following attributes:

      - max_inputfields      : (int) maximum number of answer input fields (checked in __init__
                               if not None)

      - allowed_inputfields  : list of allowed input fields (each a string) for this Response

      - required_attributes  : list of required attributes (each a string) on the main
                               response XML stanza

      - hint_tag             : xhtml tag identifying hint associated with this response inside
                               hintgroup

    """
    __metaclass__ = abc.ABCMeta  # abc = Abstract Base Class

    response_tag = None
    hint_tag = None

    max_inputfields = None
    allowed_inputfields = []
    required_attributes = []

    def __init__(self, xml, inputfields, context, system=None):
        '''
        Init is passed the following arguments:

          - xml         : ElementTree of this Response
          - inputfields : ordered list of ElementTrees for each input entry field in this Response
          - context     : script processor context
          - system      : ModuleSystem instance which provides OS, rendering, and user context

        '''
        self.xml = xml
        self.inputfields = inputfields
        self.context = context
        self.system = system

        for abox in inputfields:
            if abox.tag not in self.allowed_inputfields:
                msg = "%s: cannot have input field %s" % (unicode(self), abox.tag)
                msg += "\nSee XML source line %s" % getattr(xml, 'sourceline', '<unavailable>')
                raise LoncapaProblemError(msg)

        if self.max_inputfields and len(inputfields) > self.max_inputfields:
            msg = "%s: cannot have more than %s input fields" % (
                unicode(self), self.max_inputfields)
            msg += "\nSee XML source line %s" % getattr(xml, 'sourceline', '<unavailable>')
            raise LoncapaProblemError(msg)

        for prop in self.required_attributes:
            if not xml.get(prop):
                msg = "Error in problem specification: %s missing required attribute %s" % (
                    unicode(self), prop)
                msg += "\nSee XML source line %s" % getattr(xml, 'sourceline', '<unavailable>')
                raise LoncapaProblemError(msg)

        # ordered list of answer_id values for this response
        self.answer_ids = [x.get('id') for x in self.inputfields]
        if self.max_inputfields == 1:
            # for convenience
            self.answer_id = self.answer_ids[0]

        # map input_id -> maxpoints
        self.maxpoints = dict()
        for inputfield in self.inputfields:
            # By default, each answerfield is worth 1 point
            maxpoints = inputfield.get('points', '1')
            self.maxpoints.update({inputfield.get('id'): int(maxpoints)})

        # dict for default answer map (provided in input elements)
        self.default_answer_map = {}
        for entry in self.inputfields:
            answer = entry.get('correct_answer')
            if answer:
                self.default_answer_map[entry.get('id')] = contextualize_text(answer, self.context)

        if hasattr(self, 'setup_response'):
            self.setup_response()

    def get_max_score(self):
        '''
        Return the total maximum points of all answer fields under this Response
        '''
        return sum(self.maxpoints.values())

    def render_html(self, renderer):
        '''
        Return XHTML Element tree representation of this Response.

        Arguments:

          - renderer : procedure which produces HTML given an ElementTree
        '''
        # render ourself as a <span> + our content
        tree = etree.Element('span')
        for item in self.xml:
            # call provided procedure to do the rendering
            item_xhtml = renderer(item)
            if item_xhtml is not None:
                tree.append(item_xhtml)
        tree.tail = self.xml.tail
        return tree

    def evaluate_answers(self, student_answers, old_cmap):
        '''
        Called by capa_problem.LoncapaProblem to evaluate student answers, and to
        generate hints (if any).

        Returns the new CorrectMap, with (correctness,msg,hint,hintmode) for each answer_id.
        '''
        new_cmap = self.get_score(student_answers)
        self.get_hints(convert_files_to_filenames(student_answers), new_cmap, old_cmap)
        # log.debug('new_cmap = %s' % new_cmap)
        return new_cmap

    def get_hints(self, student_answers, new_cmap, old_cmap):
        '''
        Generate adaptive hints for this problem based on student answers, the old CorrectMap,
        and the new CorrectMap produced by get_score.

        Does not return anything.

        Modifies new_cmap, by adding hints to answer_id entries as appropriate.
        '''
        hintgroup = self.xml.find('hintgroup')
        if hintgroup is None:
            return

        # hint specified by function?
        hintfn = hintgroup.get('hintfn')
        if hintfn:
            '''
            Hint is determined by a function defined in the <script> context; evaluate
            that function to obtain list of hint, hintmode for each answer_id.

            The function should take arguments (answer_ids, student_answers, new_cmap, old_cmap)
            and it should modify new_cmap as appropriate.

            We may extend this in the future to add another argument which provides a
            callback procedure to a social hint generation system.
            '''
            if not hintfn in self.context:
                msg = 'missing specified hint function %s in script context' % hintfn
                msg += "\nSee XML source line %s" % getattr(self.xml, 'sourceline', '<unavailable>')
                raise LoncapaProblemError(msg)

            try:
                self.context[hintfn](self.answer_ids, student_answers, new_cmap, old_cmap)
            except Exception as err:
                msg = 'Error %s in evaluating hint function %s' % (err, hintfn)
                msg += "\nSee XML source line %s" % getattr(self.xml, 'sourceline', '<unavailable>')
                raise ResponseError(msg)
            return

        # hint specified by conditions and text dependent on conditions (a-la Loncapa design)
        # see http://help.loncapa.org/cgi-bin/fom?file=291
        #
        # Example:
        #
        # <formularesponse samples="x@-5:5#11" id="11" answer="$answer">
        #   <textline size="25" />
        #   <hintgroup>
        #     <formulahint samples="x@-5:5#11" answer="$wrongans" name="inversegrad"></formulahint>
        #     <hintpart on="inversegrad">
        #       <text>You have inverted the slope in the question.  The slope is
        #             (y2-y1)/(x2 - x1) you have the slope as (x2-x1)/(y2-y1).</text>
        #     </hintpart>
        #   </hintgroup>
        # </formularesponse>

        if (self.hint_tag is not None
            and hintgroup.find(self.hint_tag) is not None
            and hasattr(self, 'check_hint_condition')):

            rephints = hintgroup.findall(self.hint_tag)
            hints_to_show = self.check_hint_condition(rephints, student_answers)

            # can be 'on_request' or 'always' (default)
            hintmode = hintgroup.get('mode', 'always')
            for hintpart in hintgroup.findall('hintpart'):
                if hintpart.get('on') in hints_to_show:
                    hint_text = hintpart.find('text').text
                    # make the hint appear after the last answer box in this response
                    aid = self.answer_ids[-1]
                    new_cmap.set_hint_and_mode(aid, hint_text, hintmode)
            log.debug('after hint: new_cmap = %s' % new_cmap)

    @abc.abstractmethod
    def get_score(self, student_answers):
        '''
        Return a CorrectMap for the answers expected vs given.  This includes
        (correctness, npoints, msg) for each answer_id.

        Arguments:
         - student_answers : dict of (answer_id, answer) where answer = student input (string)
        '''
        pass

    @abc.abstractmethod
    def get_answers(self):
        '''
        Return a dict of (answer_id, answer_text) for each answer for this question.
        '''
        pass

    def check_hint_condition(self, hxml_set, student_answers):
        '''
        Return a list of hints to show.

          - hxml_set        : list of Element trees, each specifying a condition to be
                              satisfied for a named hint condition

          - student_answers : dict of student answers

        Returns a list of names of hint conditions which were satisfied.  Those are used
        to determine which hints are displayed.
        '''
        pass

    def setup_response(self):
        pass

    def __unicode__(self):
        return u'LoncapaProblem Response %s' % self.xml.tag


#-----------------------------------------------------------------------------

class JavascriptResponse(LoncapaResponse):
    """
    This response type is used when the student's answer is graded via
    Javascript using Node.js.
    """

    response_tag = 'javascriptresponse'
    max_inputfields = 1
    allowed_inputfields = ['javascriptinput']

    def setup_response(self):

        # Sets up generator, grader, display, and their dependencies.
        self.parse_xml()

        self.compile_display_javascript()

        self.params = self.extract_params()

        if self.generator:
            self.problem_state = self.generate_problem_state()
        else:
            self.problem_state = None

        self.solution = None

        self.prepare_inputfield()

    def compile_display_javascript(self):

        # TODO FIXME
        # arjun: removing this behavior for now (and likely forever). Keeping
        # until we decide on exactly how to solve this issue. For now, files are
        # manually being compiled to DATA_DIR/js/compiled.

        #latestTimestamp = 0
        #basepath = self.system.filestore.root_path + '/js/'
        #for filename in (self.display_dependencies + [self.display]):
        #    filepath = basepath + filename
        #    timestamp = os.stat(filepath).st_mtime
        #    if timestamp > latestTimestamp:
        #        latestTimestamp = timestamp
        #
        #h = hashlib.md5()
        #h.update(self.answer_id + str(self.display_dependencies))
        #compiled_filename = 'compiled/' + h.hexdigest() + '.js'
        #compiled_filepath = basepath + compiled_filename

        #if not os.path.exists(compiled_filepath) or os.stat(compiled_filepath).st_mtime < latestTimestamp:
        #    outfile = open(compiled_filepath, 'w')
        #    for filename in (self.display_dependencies + [self.display]):
        #        filepath = basepath + filename
        #        infile = open(filepath, 'r')
        #        outfile.write(infile.read())
        #        outfile.write(';\n')
        #        infile.close()
        #    outfile.close()

        # TODO this should also be fixed when the above is fixed.
        filename = self.system.ajax_url.split('/')[-1] + '.js'
        self.display_filename = 'compiled/' + filename

    def parse_xml(self):
        self.generator_xml = self.xml.xpath('//*[@id=$id]//generator',
                                            id=self.xml.get('id'))[0]

        self.grader_xml = self.xml.xpath('//*[@id=$id]//grader',
                                         id=self.xml.get('id'))[0]

        self.display_xml = self.xml.xpath('//*[@id=$id]//display',
                                         id=self.xml.get('id'))[0]

        self.xml.remove(self.generator_xml)
        self.xml.remove(self.grader_xml)
        self.xml.remove(self.display_xml)

        self.generator = self.generator_xml.get("src")
        self.grader = self.grader_xml.get("src")
        self.display = self.display_xml.get("src")

        if self.generator_xml.get("dependencies"):
            self.generator_dependencies = self.generator_xml.get("dependencies").split()
        else:
            self.generator_dependencies = []

        if self.grader_xml.get("dependencies"):
            self.grader_dependencies = self.grader_xml.get("dependencies").split()
        else:
            self.grader_dependencies = []

        if self.display_xml.get("dependencies"):
            self.display_dependencies = self.display_xml.get("dependencies").split()
        else:
            self.display_dependencies = []

        self.display_class = self.display_xml.get("class")

    def get_node_env(self):

        js_dir = os.path.join(self.system.filestore.root_path, 'js')
        tmp_env = os.environ.copy()
        node_path = self.system.node_path + ":" + os.path.normpath(js_dir)
        tmp_env["NODE_PATH"] = node_path
        return tmp_env

    def call_node(self, args):

        subprocess_args = ["node"]
        subprocess_args.extend(args)

        return subprocess.check_output(subprocess_args, env=self.get_node_env())


    def generate_problem_state(self):

        generator_file = os.path.dirname(os.path.normpath(__file__)) + '/javascript_problem_generator.js'
        output = self.call_node([generator_file,
                                 self.generator,
                                 json.dumps(self.generator_dependencies),
                                 json.dumps(str(self.context['the_lcp'].seed)),
                                 json.dumps(self.params)]).strip()

        return json.loads(output)

    def extract_params(self):

        params = {}

        for param in self.xml.xpath('//*[@id=$id]//responseparam',
                                        id=self.xml.get('id')):

            raw_param = param.get("value")
            params[param.get("name")] = json.loads(contextualize_text(raw_param, self.context))

        return params

    def prepare_inputfield(self):

        for inputfield in self.xml.xpath('//*[@id=$id]//javascriptinput',
                                        id=self.xml.get('id')):

            escapedict = {'"': '&quot;'}

            encoded_params = json.dumps(self.params)
            encoded_params = saxutils.escape(encoded_params, escapedict)
            inputfield.set("params", encoded_params)

            encoded_problem_state = json.dumps(self.problem_state)
            encoded_problem_state = saxutils.escape(encoded_problem_state,
                                                    escapedict)
            inputfield.set("problem_state", encoded_problem_state)

            inputfield.set("display_file",  self.display_filename)
            inputfield.set("display_class", self.display_class)

    def get_score(self, student_answers):
        json_submission = student_answers[self.answer_id]
        (all_correct, evaluation, solution) = self.run_grader(json_submission)
        self.solution = solution
        correctness = 'correct' if all_correct else 'incorrect'
        if all_correct:
            points = self.get_max_score()
        else:
            points = 0
        return CorrectMap(self.answer_id, correctness, npoints=points, msg=evaluation)

    def run_grader(self, submission):
        if submission is None or submission == '':
            submission = json.dumps(None)

        grader_file = os.path.dirname(os.path.normpath(__file__)) + '/javascript_problem_grader.js'
        outputs = self.call_node([grader_file,
                                  self.grader,
                                  json.dumps(self.grader_dependencies),
                                  submission,
                                  json.dumps(self.problem_state),
                                  json.dumps(self.params)]).split('\n')

        all_correct = json.loads(outputs[0].strip())
        evaluation  = outputs[1].strip()
        solution    = outputs[2].strip()
        return (all_correct, evaluation, solution)

    def get_answers(self):
        if self.solution is None:
            (_, _, self.solution) = self.run_grader(None)

        return {self.answer_id: self.solution}



#-----------------------------------------------------------------------------

class ChoiceResponse(LoncapaResponse):
    """
    This response type is used when the student chooses from a discrete set of
    choices. Currently, to be marked correct, all "correct" choices must be
    supplied by the student, and no extraneous choices may be included.

    This response type allows for two inputtypes: radiogroups and checkbox
    groups. radiogroups are used when the student should select a single answer,
    and checkbox groups are used when the student may supply 0+ answers.
    Note: it is suggested to include a "None of the above" choice when no
    answer is correct for a checkboxgroup inputtype; this ensures that a student
    must actively mark something to get credit.

    If two choices are marked as correct with a radiogroup, the student will
    have no way to get the answer right.

    TODO: Allow for marking choices as 'optional' and 'required', which would
    not penalize a student for including optional answers and would also allow
    for questions in which the student can supply one out of a set of correct
    answers.This would also allow for survey-style questions in which all
    answers are correct.

    Example:

    <choiceresponse>
        <radiogroup>
            <choice correct="false">
                <text>This is a wrong answer.</text>
            </choice>
            <choice correct="true">
                <text>This is the right answer.</text>
            </choice>
            <choice correct="false">
                <text>This is another wrong answer.</text>
            </choice>
        </radiogroup>
    </choiceresponse>

    In the above example, radiogroup can be replaced with checkboxgroup to allow
    the student to select more than one choice.

    TODO: In order for the inputtypes to render properly, this response type
    must run setup_response prior to the input type rendering. Specifically, the
    choices must be given names. This behavior seems like a leaky abstraction,
    and it'd be nice to change this at some point.

    """

    response_tag = 'choiceresponse'
    max_inputfields = 1
    allowed_inputfields = ['checkboxgroup', 'radiogroup']

    def setup_response(self):

        self.assign_choice_names()

        correct_xml = self.xml.xpath('//*[@id=$id]//choice[@correct="true"]',
                                         id=self.xml.get('id'))

        self.correct_choices = set([choice.get('name') for choice in correct_xml])

    def assign_choice_names(self):
        '''
        Initialize name attributes in <choice> tags for this response.
        '''

        for index, choice in enumerate(self.xml.xpath('//*[@id=$id]//choice',
                                                      id=self.xml.get('id'))):
            choice.set("name", "choice_" + str(index))

    def get_score(self, student_answers):

        student_answer = student_answers.get(self.answer_id, [])

        if not isinstance(student_answer, list):
            student_answer = [student_answer]

        student_answer = set(student_answer)

        required_selected = len(self.correct_choices - student_answer) == 0
        no_extra_selected = len(student_answer - self.correct_choices) == 0

        correct = required_selected & no_extra_selected

        if correct:
            return CorrectMap(self.answer_id, 'correct')
        else:
            return CorrectMap(self.answer_id, 'incorrect')

    def get_answers(self):
        return {self.answer_id: list(self.correct_choices)}

#-----------------------------------------------------------------------------


class MultipleChoiceResponse(LoncapaResponse):
    # TODO: handle direction and randomize
    snippets = [{'snippet': '''<multiplechoiceresponse direction="vertical" randomize="yes">
     <choicegroup type="MultipleChoice">
        <choice location="random" correct="false"><span>`a+b`<br/></span></choice>
        <choice location="random" correct="true"><span><math>a+b^2</math><br/></span></choice>
        <choice location="random" correct="false"><math>a+b+c</math></choice>
        <choice location="bottom" correct="false"><math>a+b+d</math></choice>
     </choicegroup>
    </multiplechoiceresponse>
    '''}]

    response_tag = 'multiplechoiceresponse'
    max_inputfields = 1
    allowed_inputfields = ['choicegroup']

    def setup_response(self):
        # call secondary setup for MultipleChoice questions, to set name attributes
        self.mc_setup_response()

        # define correct choices (after calling secondary setup)
        xml = self.xml
        cxml = xml.xpath('//*[@id=$id]//choice[@correct="true"]', id=xml.get('id'))
        self.correct_choices = [choice.get('name') for choice in cxml]

    def mc_setup_response(self):
        '''
        Initialize name attributes in <choice> stanzas in the <choicegroup> in this response.
        '''
        i = 0
        for response in self.xml.xpath("choicegroup"):
            rtype = response.get('type')
            if rtype not in ["MultipleChoice"]:
                # force choicegroup to be MultipleChoice if not valid
                response.set("type", "MultipleChoice")
            for choice in list(response):
                if choice.get("name") is None:
                    choice.set("name", "choice_" + str(i))
                    i += 1
                else:
                    choice.set("name", "choice_" + choice.get("name"))

    def get_score(self, student_answers):
        '''
        grade student response.
        '''
        # log.debug('%s: student_answers=%s, correct_choices=%s' % (
        #   unicode(self), student_answers, self.correct_choices))
        if (self.answer_id in student_answers
            and student_answers[self.answer_id] in self.correct_choices):
            return CorrectMap(self.answer_id, 'correct')
        else:
            return CorrectMap(self.answer_id, 'incorrect')

    def get_answers(self):
        return {self.answer_id: self.correct_choices}


class TrueFalseResponse(MultipleChoiceResponse):

    response_tag = 'truefalseresponse'

    def mc_setup_response(self):
        i = 0
        for response in self.xml.xpath("choicegroup"):
            response.set("type", "TrueFalse")
            for choice in list(response):
                if choice.get("name") is None:
                    choice.set("name", "choice_" + str(i))
                    i += 1
                else:
                    choice.set("name", "choice_" + choice.get("name"))

    def get_score(self, student_answers):
        correct = set(self.correct_choices)
        answers = set(student_answers.get(self.answer_id, []))

        if correct == answers:
            return CorrectMap(self.answer_id, 'correct')

        return CorrectMap(self.answer_id, 'incorrect')

#-----------------------------------------------------------------------------


class OptionResponse(LoncapaResponse):
    '''
    TODO: handle direction and randomize
    '''
    snippets = [{'snippet': """<optionresponse direction="vertical" randomize="yes">
        <optioninput options="('Up','Down')" correct="Up">
          <text>The location of the sky</text>
        </optioninput>
        <optioninput options="('Up','Down')" correct="Down">
          <text>The location of the earth</text>
        </optioninput>
    </optionresponse>"""}]

    response_tag = 'optionresponse'
    hint_tag = 'optionhint'
    allowed_inputfields = ['optioninput']

    def setup_response(self):
        self.answer_fields = self.inputfields

    def get_score(self, student_answers):
        # log.debug('%s: student_answers=%s' % (unicode(self),student_answers))
        cmap = CorrectMap()
        amap = self.get_answers()
        for aid in amap:
            if aid in student_answers and student_answers[aid] == amap[aid]:
                cmap.set(aid, 'correct')
            else:
                cmap.set(aid, 'incorrect')
        return cmap

    def get_answers(self):
        amap = dict([(af.get('id'), af.get('correct')) for af in self.answer_fields])
        # log.debug('%s: expected answers=%s' % (unicode(self),amap))
        return amap

#-----------------------------------------------------------------------------


class NumericalResponse(LoncapaResponse):

    response_tag = 'numericalresponse'
    hint_tag = 'numericalhint'
    allowed_inputfields = ['textline']
    required_attributes = ['answer']
    max_inputfields = 1

    def setup_response(self):
        xml = self.xml
        context = self.context
        self.correct_answer = contextualize_text(xml.get('answer'), context)
        try:
            self.tolerance_xml = xml.xpath('//*[@id=$id]//responseparam[@type="tolerance"]/@default',
                                           id=xml.get('id'))[0]
            self.tolerance = contextualize_text(self.tolerance_xml, context)
        except Exception:
            self.tolerance = '0'
        try:
            self.answer_id = xml.xpath('//*[@id=$id]//textline/@id',
                                       id=xml.get('id'))[0]
        except Exception:
            self.answer_id = None

    def get_score(self, student_answers):
        '''Grade a numeric response '''
        student_answer = student_answers[self.answer_id]

        try:
            correct_ans = complex(self.correct_answer)
        except ValueError:
            log.debug("Content error--answer '{0}' is not a valid complex number".format(self.correct_answer))
            raise StudentInputError("There was a problem with the staff answer to this problem")

        try:
            correct = compare_with_tolerance(evaluator(dict(), dict(), student_answer),
                                             correct_ans, self.tolerance)
        # We should catch this explicitly.
        # I think this is just pyparsing.ParseException, calc.UndefinedVariable:
        # But we'd need to confirm
        except:
            # Use the traceback-preserving version of re-raising with a different type
            import sys
            type, value, traceback = sys.exc_info()

            raise StudentInputError, ("Invalid input: could not interpret '%s' as a number" %
                                      cgi.escape(student_answer)), traceback

        if correct:
            return CorrectMap(self.answer_id, 'correct')
        else:
            return CorrectMap(self.answer_id, 'incorrect')

    # TODO: add check_hint_condition(self, hxml_set, student_answers)

    def get_answers(self):
        return {self.answer_id: self.correct_answer}

#-----------------------------------------------------------------------------


class StringResponse(LoncapaResponse):

    response_tag = 'stringresponse'
    hint_tag = 'stringhint'
    allowed_inputfields = ['textline']
    required_attributes = ['answer']
    max_inputfields = 1

    def setup_response(self):
        self.correct_answer = contextualize_text(self.xml.get('answer'), self.context).strip()

    def get_score(self, student_answers):
        '''Grade a string response '''
        student_answer = student_answers[self.answer_id].strip()
        correct = self.check_string(self.correct_answer, student_answer)
        return CorrectMap(self.answer_id, 'correct' if correct else 'incorrect')

    def check_string(self, expected, given):
        if self.xml.get('type') == 'ci': return given.lower() == expected.lower()
        return given == expected

    def check_hint_condition(self, hxml_set, student_answers):
        given = student_answers[self.answer_id].strip()
        hints_to_show = []
        for hxml in hxml_set:
            name = hxml.get('name')
            correct_answer = contextualize_text(hxml.get('answer'), self.context).strip()
            if self.check_string(correct_answer, given): hints_to_show.append(name)
        log.debug('hints_to_show = %s' % hints_to_show)
        return hints_to_show

    def get_answers(self):
        return {self.answer_id: self.correct_answer}

#-----------------------------------------------------------------------------


class CustomResponse(LoncapaResponse):
    '''
    Custom response.  The python code to be run should be in <answer>...</answer>
    or in a <script>...</script>
    '''
    snippets = [{'snippet': """<customresponse>
    <text>
    <br/>
    Suppose that \(I(t)\) rises from \(0\) to \(I_S\) at a time \(t_0 \neq 0\)
    In the space provided below write an algebraic expression for \(I(t)\).
    <br/>
    <textline size="5" correct_answer="IS*u(t-t0)" />
    </text>
    <answer type="loncapa/python">
    correct=['correct']
    try:
        r = str(submission[0])
    except ValueError:
        correct[0] ='incorrect'
        r = '0'
    if not(r=="IS*u(t-t0)"):
        correct[0] ='incorrect'
    </answer>
    </customresponse>"""},
    {'snippet': """<script type="loncapa/python"><![CDATA[

def sympy_check2():
  messages[0] = '%s:%s' % (submission[0],fromjs[0].replace('<','&lt;'))
  #messages[0] = str(answers)
  correct[0] = 'correct'

]]>
</script>

  <customresponse cfn="sympy_check2" type="cs" expect="2.27E-39" dojs="math" size="30" answer="2.27E-39">
    <textline size="40" dojs="math" />
    <responseparam description="Numerical Tolerance" type="tolerance" default="0.00001" name="tol"/>
  </customresponse>"""}]

    response_tag = 'customresponse'

    allowed_inputfields = ['textline', 'textbox', 'crystallography', 'chemicalequationinput', 'vsepr_input']

    def setup_response(self):
        xml = self.xml

        # if <customresponse> has an "expect" (or "answer") attribute then save that
        self.expect = xml.get('expect') or xml.get('answer')
        self.myid = xml.get('id')

        log.debug('answer_ids=%s' % self.answer_ids)

        # the <answer>...</answer> stanza should be local to the current <customresponse>.
        # So try looking there first.
        self.code = None
        answer = None
        try:
            answer = xml.xpath('//*[@id=$id]//answer', id=xml.get('id'))[0]
        except IndexError:
            # print "xml = ",etree.tostring(xml,pretty_print=True)

            # if we have a "cfn" attribute then look for the function specified by cfn, in
            # the problem context ie the comparison function is defined in the
            # <script>...</script> stanza instead
            cfn = xml.get('cfn')
            if cfn:
                log.debug("cfn = %s" % cfn)
                if cfn in self.context:
                    self.code = self.context[cfn]
                else:
                    msg = "%s: can't find cfn %s in context" % (unicode(self), cfn)
                    msg += "\nSee XML source line %s" % getattr(self.xml, 'sourceline',
                                                                '<unavailable>')
                    raise LoncapaProblemError(msg)

        if not self.code:
            if answer is None:
                log.error("[courseware.capa.responsetypes.customresponse] missing"
                          " code checking script! id=%s" % self.myid)
                self.code = ''
            else:
                answer_src = answer.get('src')
                if answer_src is not None:
                    self.code = self.system.filesystem.open('src/' + answer_src).read()
                else:
                    self.code = answer.text

    def get_score(self, student_answers):
        '''
        student_answers is a dict with everything from request.POST, but with the first part
        of each key removed (the string before the first "_").
        '''

        log.debug('%s: student_answers=%s' % (unicode(self), student_answers))

        # ordered list of answer id's
        idset = sorted(self.answer_ids)
        try:
            # ordered list of answers
            submission = [student_answers[k] for k in idset]
        except Exception as err:
            msg = ('[courseware.capa.responsetypes.customresponse] error getting'
                   ' student answer from %s' % student_answers)
            msg += '\n idset = %s, error = %s' % (idset, err)
            log.error(msg)
            raise Exception(msg)

        # global variable in context which holds the Presentation MathML from dynamic math input
        # ordered list of dynamath responses
        dynamath = [student_answers.get(k + '_dynamath', None) for k in idset]

        # if there is only one box, and it's empty, then don't evaluate
        if len(idset) == 1 and not submission[0]:
            # default to no error message on empty answer (to be consistent with other
            # responsetypes) but allow author to still have the old behavior by setting
            # empty_answer_err attribute
            msg = ('<span class="inline-error">No answer entered!</span>'
                   if self.xml.get('empty_answer_err') else '')
            return CorrectMap(idset[0], 'incorrect', msg=msg)

        # NOTE: correct = 'unknown' could be dangerous. Inputtypes such as textline are
        # not expecting 'unknown's
        correct = ['unknown'] * len(idset)
        messages = [''] * len(idset)

        # put these in the context of the check function evaluator
        # note that this doesn't help the "cfn" version - only the exec version
        self.context.update({
            # our subtree
            'xml': self.xml,

            # my ID
            'response_id': self.myid,

            # expected answer (if given as attribute)
            'expect': self.expect,

            # ordered list of student answers from entry boxes in our subtree
            'submission': submission,

            # ordered list of ID's of all entry boxes in our subtree
            'idset': idset,

            # ordered list of all javascript inputs in our subtree
            'dynamath': dynamath,

            # dict of student's responses, with keys being entry box IDs
            'answers': student_answers,

            # the list to be filled in by the check function
            'correct': correct,

            # the list of messages to be filled in by the check function
            'messages': messages,

            # any options to be passed to the cfn
            'options': self.xml.get('options'),
            'testdat': 'hello world',
            })

        # pass self.system.debug to cfn
        self.context['debug'] = self.system.DEBUG

        # exec the check function
        if type(self.code) == str:
            try:
                exec self.code in self.context['global_context'], self.context
                correct = self.context['correct']
                messages = self.context['messages']
            except Exception as err:
                print "oops in customresponse (code) error %s" % err
                print "context = ", self.context
                print traceback.format_exc()
                # Notify student
                raise StudentInputError("Error: Problem could not be evaluated with your input")
        else:
            # self.code is not a string; assume its a function

            # this is an interface to the Tutor2 check functions
            fn = self.code
            ret = None
            log.debug(" submission = %s" % submission)
            try:
                answer_given = submission[0] if (len(idset) == 1) else submission
                # handle variable number of arguments in check function, for backwards compatibility
                # with various Tutor2 check functions
                args = [self.expect, answer_given, student_answers, self.answer_ids[0]]
                argspec = inspect.getargspec(fn)
                nargs = len(argspec.args) - len(argspec.defaults or [])
                kwargs = {}
                for argname in argspec.args[nargs:]:
                    kwargs[argname] = self.context[argname] if argname in self.context else None

                log.debug('[customresponse] answer_given=%s' % answer_given)
                log.debug('nargs=%d, args=%s, kwargs=%s' % (nargs, args, kwargs))

                ret = fn(*args[:nargs], **kwargs)
            except Exception as err:
                log.error("oops in customresponse (cfn) error %s" % err)
                # print "context = ",self.context
                log.error(traceback.format_exc())
                raise Exception("oops in customresponse (cfn) error %s" % err)
            log.debug("[courseware.capa.responsetypes.customresponse.get_score] ret = %s" % ret)
            if type(ret) == dict:
                correct = ['correct'] * len(idset) if ret['ok'] else ['incorrect'] * len(idset)
                msg = ret['msg']

                if 1:
                    # try to clean up message html
                    msg = '<html>' + msg + '</html>'
                    msg = msg.replace('&#60;', '&lt;')
                    #msg = msg.replace('&lt;','<')
                    msg = etree.tostring(fromstring_bs(msg, convertEntities=None),
                                         pretty_print=True)
                    #msg = etree.tostring(fromstring_bs(msg),pretty_print=True)
                    msg = msg.replace('&#13;', '')
                    #msg = re.sub('<html>(.*)</html>','\\1',msg,flags=re.M|re.DOTALL)	# python 2.7
                    msg = re.sub('(?ms)<html>(.*)</html>', '\\1', msg)

                messages[0] = msg
            else:
                correct = ['correct'] * len(idset) if ret else ['incorrect'] * len(idset)

        # build map giving "correct"ness of the answer(s)
        correct_map = CorrectMap()
        for k in range(len(idset)):
            npoints = self.maxpoints[idset[k]] if correct[k] == 'correct' else 0
            correct_map.set(idset[k], correct[k], msg=messages[k],
                            npoints=npoints)
        return correct_map

    def get_answers(self):
        '''
        Give correct answer expected for this response.

        use default_answer_map from entry elements (eg textline),
        when this response has multiple entry objects.

        but for simplicity, if an "expect" attribute was given by the content author
        ie <customresponse expect="foo" ...> then that.
        '''
        if len(self.answer_ids) > 1:
            return self.default_answer_map
        if self.expect:
            return {self.answer_ids[0]: self.expect}
        return self.default_answer_map

#-----------------------------------------------------------------------------


class SymbolicResponse(CustomResponse):
    """
    Symbolic math response checking, using symmath library.
    """
    snippets = [{'snippet': '''<problem>
      <text>Compute \[ \exp\left(-i \frac{\theta}{2} \left[ \begin{matrix} 0 & 1 \\ 1 & 0 \end{matrix} \right] \right) \]
      and give the resulting \(2\times 2\) matrix: <br/>
        <symbolicresponse answer="">
          <textline size="40" math="1" />
        </symbolicresponse>
      <br/>
      Your input should be typed in as a list of lists, eg <tt>[[1,2],[3,4]]</tt>.
      </text>
    </problem>'''}]

    response_tag = 'symbolicresponse'

    def setup_response(self):
        self.xml.set('cfn', 'symmath_check')
        code = "from symmath import *"
        exec code in self.context, self.context
        CustomResponse.setup_response(self)

#-----------------------------------------------------------------------------

"""
valid:       Flag indicating valid score_msg format (Boolean)
correct:     Correctness of submission (Boolean)
score:       Points to be assigned (numeric, can be float)
msg:         Message from grader to display to student (string)
"""
ScoreMessage = namedtuple('ScoreMessage',
                          ['valid', 'correct', 'points', 'msg'])


class CodeResponse(LoncapaResponse):
    """
    Grade student code using an external queueing server, called 'xqueue'

    Expects 'xqueue' dict in ModuleSystem with the following keys that are needed by CodeResponse:
        system.xqueue = { 'interface': XqueueInterface object,
                          'callback_url': Per-StudentModule callback URL
                                          where results are posted (string),
                          'default_queuename': Default queuename to submit request (string)
                        }

    External requests are only submitted for student submission grading
        (i.e. and not for getting reference answers)
    """

    response_tag = 'coderesponse'
    allowed_inputfields = ['textbox', 'filesubmission']
    max_inputfields = 1

    def setup_response(self):
        '''
        Configure CodeResponse from XML. Supports both CodeResponse and ExternalResponse XML

        TODO: Determines whether in synchronous or asynchronous (queued) mode
        '''
        xml = self.xml
        # TODO: XML can override external resource (grader/queue) URL
        self.url = xml.get('url', None)
        self.queue_name = xml.get('queuename', self.system.xqueue['default_queuename'])

        # VS[compat]:
        #   Check if XML uses the ExternalResponse format or the generic CodeResponse format
        codeparam = self.xml.find('codeparam')
        if codeparam is None:
            self._parse_externalresponse_xml()
        else:
            self._parse_coderesponse_xml(codeparam)

    def _parse_coderesponse_xml(self, codeparam):
        '''
        Parse the new CodeResponse XML format. When successful, sets:
            self.initial_display
            self.answer (an answer to display to the student in the LMS)
            self.payload
        '''
        # Note that CodeResponse is agnostic to the specific contents of grader_payload
        grader_payload = codeparam.find('grader_payload')
        grader_payload = grader_payload.text if grader_payload is not None else ''
        self.payload = {'grader_payload': grader_payload}

        self.initial_display = find_with_default(codeparam, 'initial_display', '')
        self.answer = find_with_default(codeparam, 'answer_display',
                                        'No answer provided.')

    def _parse_externalresponse_xml(self):
        '''
        VS[compat]: Suppport for old ExternalResponse XML format. When successful, sets:
            self.initial_display
            self.answer (an answer to display to the student in the LMS)
            self.payload
        '''
        answer = self.xml.find('answer')

        if answer is not None:
            answer_src = answer.get('src')
            if answer_src is not None:
                code = self.system.filesystem.open('src/' + answer_src).read()
            else:
                code = answer.text
        else:  # no <answer> stanza; get code from <script>
            code = self.context['script_code']
            if not code:
                msg = '%s: Missing answer script code for coderesponse' % unicode(self)
                msg += "\nSee XML source line %s" % getattr(self.xml, 'sourceline', '<unavailable>')
                raise LoncapaProblemError(msg)

        tests = self.xml.get('tests')

        # Extract 'answer' and 'initial_display' from XML. Note that the code to be exec'ed here is:
        #   (1) Internal edX code, i.e. NOT student submissions, and
        #   (2) The code should only define the strings 'initial_display', 'answer',
        #           'preamble', 'test_program'
        #           following the ExternalResponse XML format
        penv = {}
        penv['__builtins__'] = globals()['__builtins__']
        try:
            exec(code, penv, penv)
        except Exception as err:
            log.error('Error in CodeResponse %s: Error in problem reference code' % err)
            raise Exception(err)
        try:
            self.answer = penv['answer']
            self.initial_display = penv['initial_display']
        except Exception as err:
            log.error("Error in CodeResponse %s: Problem reference code does not define"
                      " 'answer' and/or 'initial_display' in <answer>...</answer>" % err)
            raise Exception(err)

        # Finally, make the ExternalResponse input XML format conform to the generic
        # exteral grader interface
        #   The XML tagging of grader_payload is pyxserver-specific
        grader_payload  = '<pyxserver>'
        grader_payload += '<tests>' + tests + '</tests>\n'
        grader_payload += '<processor>' + code + '</processor>'
        grader_payload += '</pyxserver>'
        self.payload = {'grader_payload': grader_payload}

    def get_score(self, student_answers):
        try:
            # Note that submission can be a file
            submission = student_answers[self.answer_id]
        except Exception as err:
            log.error('Error in CodeResponse %s: cannot get student answer for %s;'
                      ' student_answers=%s' %
                (err, self.answer_id, convert_files_to_filenames(student_answers)))
            raise Exception(err)

        # Prepare xqueue request
        #------------------------------------------------------------

        qinterface = self.system.xqueue['interface']
        qtime = datetime.strftime(datetime.now(), xqueue_interface.dateformat)

        anonymous_student_id = self.system.anonymous_student_id

        # Generate header
        queuekey = xqueue_interface.make_hashkey(str(self.system.seed) + qtime +
                                                 anonymous_student_id +
                                                 self.answer_id)
        xheader = xqueue_interface.make_xheader(lms_callback_url=self.system.xqueue['callback_url'],
                                                lms_key=queuekey,
                                                queue_name=self.queue_name)

        # Generate body
        if is_list_of_files(submission):
            # TODO: Get S3 pointer from the Queue
            self.context.update({'submission': ''})
        else:
            self.context.update({'submission': submission})

        contents = self.payload.copy()

        # Metadata related to the student submission revealed to the external grader
        student_info = {'anonymous_student_id': anonymous_student_id,
                        'submission_time': qtime,
                       }
        contents.update({'student_info': json.dumps(student_info)})

        # Submit request. When successful, 'msg' is the prior length of the queue
        if is_list_of_files(submission):
            # TODO: Is there any information we want to send here?
            contents.update({'student_response': ''})
            (error, msg) = qinterface.send_to_queue(header=xheader,
                                                    body=json.dumps(contents),
                                                    files_to_upload=submission)
        else:
            contents.update({'student_response': submission})
            (error, msg) = qinterface.send_to_queue(header=xheader,
                                                    body=json.dumps(contents))

        # State associated with the queueing request
        queuestate = {'key': queuekey,
                      'time': qtime,}

        cmap = CorrectMap()
        if error:
            cmap.set(self.answer_id, queuestate=None,
                     msg='Unable to deliver your submission to grader. (Reason: %s.)'
                         ' Please try again later.' % msg)
        else:
            # Queueing mechanism flags:
            #   1) Backend: Non-null CorrectMap['queuestate'] indicates that
            #      the problem has been queued
            #   2) Frontend: correctness='incomplete' eventually trickles down
            #      through inputtypes.textbox and .filesubmission to inform the
            #      browser to poll the LMS
            cmap.set(self.answer_id, queuestate=queuestate, correctness='incomplete', msg=msg)

        return cmap

    def update_score(self, score_msg, oldcmap, queuekey):

        (valid_score_msg, correct, points, msg) = self._parse_score_msg(score_msg)
        if not valid_score_msg:
            oldcmap.set(self.answer_id,
                        msg='Invalid grader reply. Please contact the course staff.')
            return oldcmap

        correctness = 'correct' if correct else 'incorrect'

        # TODO: Find out how this is used elsewhere, if any
        self.context['correct'] = correctness

        # Replace 'oldcmap' with new grading results if queuekey matches.  If queuekey
        # does not match, we keep waiting for the score_msg whose key actually matches
        if oldcmap.is_right_queuekey(self.answer_id, queuekey):
            # Sanity check on returned points
            if points < 0:
                points = 0
            # Queuestate is consumed
            oldcmap.set(self.answer_id, npoints=points, correctness=correctness,
                        msg=msg.replace('&nbsp;', '&#160;'), queuestate=None)
        else:
            log.debug('CodeResponse: queuekey %s does not match for answer_id=%s.' %
                      (queuekey, self.answer_id))

        return oldcmap

    def get_answers(self):
        anshtml = '<span class="code-answer"><pre><code>%s</code></pre></span>' % self.answer
        return {self.answer_id: anshtml}

    def get_initial_display(self):
        return {self.answer_id: self.initial_display}

    def _parse_score_msg(self, score_msg):
        """
         Grader reply is a JSON-dump of the following dict
           { 'correct': True/False,
             'score': Numeric value (floating point is okay) to assign to answer
             'msg': grader_msg }

        Returns (valid_score_msg, correct, score, msg):
            valid_score_msg: Flag indicating valid score_msg format (Boolean)
            correct:         Correctness of submission (Boolean)
            score:           Points to be assigned (numeric, can be float)
            msg:             Message from grader to display to student (string)
        """
        fail = (False, False, 0, '')
        try:
            score_result = json.loads(score_msg)
        except (TypeError, ValueError):
            log.error("External grader message should be a JSON-serialized dict."
                      " Received score_msg = %s" % score_msg)
            return fail
        if not isinstance(score_result, dict):
            log.error("External grader message should be a JSON-serialized dict."
                      " Received score_result = %s" % score_result)
            return fail
        for tag in ['correct', 'score', 'msg']:
            if tag not in score_result:
                log.error("External grader message is missing one or more required"
                          " tags: 'correct', 'score', 'msg'")
                return fail

        # Next, we need to check that the contents of the external grader message
        #   is safe for the LMS.
        # 1) Make sure that the message is valid XML (proper opening/closing tags)
        # 2) TODO: Is the message actually HTML?
        msg = score_result['msg']
        try:
            etree.fromstring(msg)
        except etree.XMLSyntaxError as err:
            log.error("Unable to parse external grader message as valid"
                      " XML: score_msg['msg']=%s" % msg)
            return fail

        return (True, score_result['correct'], score_result['score'], msg)


#-----------------------------------------------------------------------------


class ExternalResponse(LoncapaResponse):
    '''
    Grade the students input using an external server.

    Typically used by coding problems.

    '''
    snippets = [{'snippet': '''<externalresponse tests="repeat:10,generate">
    <textbox rows="10" cols="70"  mode="python"/>
    <answer><![CDATA[
initial_display = """
def inc(x):
"""

answer = """
def inc(n):
    return n+1
"""
preamble = """
import sympy
"""
test_program = """
import random

def testInc(n = None):
    if n is None:
       n = random.randint(2, 20)
    print 'Test is: inc(%d)'%n
    return str(inc(n))

def main():
   f = os.fdopen(3,'w')
   test = int(sys.argv[1])
   rndlist = map(int,os.getenv('rndlist').split(','))
   random.seed(rndlist[0])
   if test == 1: f.write(testInc(0))
   elif test == 2: f.write(testInc(1))
   else:  f.write(testInc())
   f.close()

main()
"""
]]>
    </answer>
  </externalresponse>'''}]

    response_tag = 'externalresponse'
    allowed_inputfields = ['textline', 'textbox']

    def setup_response(self):
        xml = self.xml
        # FIXME - hardcoded URL
        self.url = xml.get('url') or "http://qisx.mit.edu:8889/pyloncapa"

        answer = xml.find('answer')
        if answer is not None:
            answer_src = answer.get('src')
            if answer_src is not None:
                self.code = self.system.filesystem.open('src/' + answer_src).read()
            else:
                self.code = answer.text
        else:
            # no <answer> stanza; get code from <script>
            self.code = self.context['script_code']
            if not self.code:
                msg = '%s: Missing answer script code for externalresponse' % unicode(self)
                msg += "\nSee XML source line %s" % getattr(self.xml, 'sourceline', '<unavailable>')
                raise LoncapaProblemError(msg)

        self.tests = xml.get('tests')

    def do_external_request(self, cmd, extra_payload):
        '''
        Perform HTTP request / post to external server.

        cmd = remote command to perform (str)
        extra_payload = dict of extra stuff to post.

        Return XML tree of response (from response body)
        '''
        xmlstr = etree.tostring(self.xml, pretty_print=True)
        payload = {'xml': xmlstr,
                   'edX_cmd': cmd,
                   'edX_tests': self.tests,
                   'processor': self.code,
                   }
        payload.update(extra_payload)

        try:
            # call external server. TODO: synchronous call, can block for a long time
            r = requests.post(self.url, data=payload)
        except Exception as err:
            msg = 'Error %s - cannot connect to external server url=%s' % (err, self.url)
            log.error(msg)
            raise Exception(msg)

        if self.system.DEBUG:
            log.info('response = %s' % r.text)

        if (not r.text) or (not r.text.strip()):
            raise Exception('Error: no response from external server url=%s' % self.url)

        try:
            # response is XML; parse it
            rxml = etree.fromstring(r.text)
        except Exception as err:
            msg = 'Error %s - cannot parse response from external server r.text=%s' % (err, r.text)
            log.error(msg)
            raise Exception(msg)

        return rxml

    def get_score(self, student_answers):
        idset = sorted(self.answer_ids)
        cmap = CorrectMap()
        try:
            submission = [student_answers[k] for k in idset]
        except Exception as err:
            log.error('Error %s: cannot get student answer for %s; student_answers=%s' %
                      (err, self.answer_ids, student_answers))
            raise Exception(err)

        self.context.update({'submission': submission})

        extra_payload = {'edX_student_response': json.dumps(submission)}

        try:
            rxml = self.do_external_request('get_score', extra_payload)
        except Exception as err:
            log.error('Error %s' % err)
            if self.system.DEBUG:
                cmap.set_dict(dict(zip(sorted(self.answer_ids), ['incorrect'] * len(idset))))
                cmap.set_property(
                    self.answer_ids[0], 'msg',
                    '<span class="inline-error">%s</span>' % str(err).replace('<', '&lt;'))
                return cmap

        ad = rxml.find('awarddetail').text
        admap = {'EXACT_ANS': 'correct',         # TODO: handle other loncapa responses
                 'WRONG_FORMAT': 'incorrect',
                 }
        self.context['correct'] = ['correct']
        if ad in admap:
            self.context['correct'][0] = admap[ad]

        # create CorrectMap
        for key in idset:
            idx = idset.index(key)
            msg = rxml.find('message').text.replace('&nbsp;', '&#160;') if idx == 0 else None
            cmap.set(key, self.context['correct'][idx], msg=msg)

        return cmap

    def get_answers(self):
        '''
        Use external server to get expected answers
        '''
        try:
            rxml = self.do_external_request('get_answers', {})
            exans = json.loads(rxml.find('expected').text)
        except Exception as err:
            log.error('Error %s' % err)
            if self.system.DEBUG:
                msg = '<span class="inline-error">%s</span>' % str(err).replace('<', '&lt;')
                exans = [''] * len(self.answer_ids)
                exans[0] = msg

        if not (len(exans) == len(self.answer_ids)):
            log.error('Expected %d answers from external server, only got %d!' %
                      (len(self.answer_ids), len(exans)))
            raise Exception('Short response from external server')
        return dict(zip(self.answer_ids, exans))


#-----------------------------------------------------------------------------

class FormulaResponse(LoncapaResponse):
    '''
    Checking of symbolic math response using numerical sampling.
    '''
    snippets = [{'snippet': '''<problem>

    <script type="loncapa/python">
    I = "m*c^2"
    </script>

    <text>
    <br/>
    Give an equation for the relativistic energy of an object with mass m.
    </text>
    <formularesponse type="cs" samples="m,c@1,2:3,4#10" answer="$I">
      <responseparam description="Numerical Tolerance" type="tolerance"
                   default="0.00001" name="tol" />
      <textline size="40" math="1" />
    </formularesponse>

    </problem>'''}]

    response_tag = 'formularesponse'
    hint_tag = 'formulahint'
    allowed_inputfields = ['textline']
    required_attributes = ['answer']
    max_inputfields = 1

    def setup_response(self):
        xml = self.xml
        context = self.context
        self.correct_answer = contextualize_text(xml.get('answer'), context)
        self.samples = contextualize_text(xml.get('samples'), context)
        try:
            self.tolerance_xml = xml.xpath('//*[@id=$id]//responseparam[@type="tolerance"]/@default',
                                           id=xml.get('id'))[0]
            self.tolerance = contextualize_text(self.tolerance_xml, context)
        except Exception:
            self.tolerance = '0.00001'

        ts = xml.get('type')
        if ts is None:
            typeslist = []
        else:
            typeslist = ts.split(',')
        if 'ci' in typeslist:
            # Case insensitive
            self.case_sensitive = False
        elif 'cs' in typeslist:
            # Case sensitive
            self.case_sensitive = True
        else:
            # Default
            self.case_sensitive = False

    def get_score(self, student_answers):
        given = student_answers[self.answer_id]
        correctness = self.check_formula(self.correct_answer, given, self.samples)
        return CorrectMap(self.answer_id, correctness)

    def check_formula(self, expected, given, samples):
        variables = samples.split('@')[0].split(',')
        numsamples = int(samples.split('@')[1].split('#')[1])
        sranges = zip(*map(lambda x: map(float, x.split(",")),
                         samples.split('@')[1].split('#')[0].split(':')))

        ranges = dict(zip(variables, sranges))
        for i in range(numsamples):
            instructor_variables = self.strip_dict(dict(self.context))
            student_variables = dict()
            # ranges give numerical ranges for testing
            for var in ranges:
                value = random.uniform(*ranges[var])
                instructor_variables[str(var)] = value
                student_variables[str(var)] = value
            #log.debug('formula: instructor_vars=%s, expected=%s' % (instructor_variables,expected))
            instructor_result = evaluator(instructor_variables, dict(),
                                          expected, cs=self.case_sensitive)
            try:
                #log.debug('formula: student_vars=%s, given=%s' % (student_variables,given))
                student_result = evaluator(student_variables,
                                           dict(),
                                           given,
                                           cs=self.case_sensitive)
            except UndefinedVariable as uv:
                log.debug('formularesponse: undefined variable in given=%s' % given)
                raise StudentInputError("Invalid input: " + uv.message + " not permitted in answer")
            except Exception as err:
                #traceback.print_exc()
                log.debug('formularesponse: error %s in formula' % err)
                raise StudentInputError("Invalid input: Could not parse '%s' as a formula" %\
                                        cgi.escape(given))
            if numpy.isnan(student_result) or numpy.isinf(student_result):
                return "incorrect"
            if not compare_with_tolerance(student_result, instructor_result, self.tolerance):
                return "incorrect"
        return "correct"

    def strip_dict(self, d):
        ''' Takes a dict. Returns an identical dict, with all non-word
        keys and all non-numeric values stripped out. All values also
        converted to float. Used so we can safely use Python contexts.
        '''
        d = dict([(k, numpy.complex(d[k])) for k in d if type(k) == str and
                  k.isalnum() and
                  isinstance(d[k], numbers.Number)])
        return d

    def check_hint_condition(self, hxml_set, student_answers):
        given = student_answers[self.answer_id]
        hints_to_show = []
        for hxml in hxml_set:
            samples = hxml.get('samples')
            name = hxml.get('name')
            correct_answer = contextualize_text(hxml.get('answer'), self.context)
            try:
                correctness = self.check_formula(correct_answer, given, samples)
            except Exception:
                correctness = 'incorrect'
            if correctness == 'correct':
                hints_to_show.append(name)
        log.debug('hints_to_show = %s' % hints_to_show)
        return hints_to_show

    def get_answers(self):
        return {self.answer_id: self.correct_answer}

#-----------------------------------------------------------------------------


class SchematicResponse(LoncapaResponse):

    response_tag = 'schematicresponse'
    allowed_inputfields = ['schematic']

    def setup_response(self):
        xml = self.xml
        answer = xml.xpath('//*[@id=$id]//answer', id=xml.get('id'))[0]
        answer_src = answer.get('src')
        if answer_src is not None:
            # Untested; never used
            self.code = self.system.filestore.open('src/' + answer_src).read()
        else:
            self.code = answer.text

    def get_score(self, student_answers):
        from capa_problem import global_context
        submission = [json.loads(student_answers[k]) for k in sorted(self.answer_ids)]
        self.context.update({'submission': submission})
        exec self.code in global_context, self.context
        cmap = CorrectMap()
        cmap.set_dict(dict(zip(sorted(self.answer_ids), self.context['correct'])))
        return cmap

    def get_answers(self):
        # use answers provided in input elements
        return self.default_answer_map

#-----------------------------------------------------------------------------


class ImageResponse(LoncapaResponse):
    """
    Handle student response for image input: the input is a click on an image,
    which produces an [x,y] coordinate pair.  The click is correct if it falls
    within a region specified.  This region is a union of rectangles.

    Lon-CAPA requires that each <imageresponse> has a <foilgroup> inside it.
    That doesn't make sense to me (Ike).  Instead, let's have it such that
    <imageresponse> should contain one or more <imageinput> stanzas.
    Each <imageinput> should specify a rectangle(s) or region(s), given as an
    attribute, defining the correct answer.

    <imageinput src="/static/images/Lecture2/S2_p04.png" width="811" height="610"
    rectangle="(10,10)-(20,30);(12,12)-(40,60)"
    regions="[[[10,10], [20,30], [40, 10]], [[100,100], [120,130], [110,150]]]"/>

    Regions is list of lists [region1, region2, region3, ...] where regionN
    is disordered list of points: [[1,1], [100,100], [50,50], [20, 70]].

    If there is only one region in the list, simpler notation can be used:
    regions="[[10,10], [30,30], [10, 30], [30, 10]]" (without explicitly
        setting outer list)

    Returns:
        True, if click is inside any region or rectangle. Otherwise False.
    """
    snippets = [{'snippet': '''<imageresponse>
      <imageinput src="image1.jpg" width="200" height="100"
      rectangle="(10,10)-(20,30)" />
      <imageinput src="image2.jpg" width="210" height="130"
      rectangle="(12,12)-(40,60)" />
      <imageinput src="image3.jpg" width="210" height="130"
      rectangle="(10,10)-(20,30);(12,12)-(40,60)" />
      <imageinput src="image4.jpg" width="811" height="610"
      rectangle="(10,10)-(20,30);(12,12)-(40,60)"
      regions="[[[10,10], [20,30], [40, 10]], [[100,100], [120,130], [110,150]]]"/>
      <imageinput src="image5.jpg" width="200" height="200"
      regions="[[[10,10], [20,30], [40, 10]], [[100,100], [120,130], [110,150]]]"/>
    </imageresponse>'''}]

    response_tag = 'imageresponse'
    allowed_inputfields = ['imageinput']

    def setup_response(self):
        self.ielements = self.inputfields
        self.answer_ids = [ie.get('id') for ie in self.ielements]

    def get_score(self, student_answers):
        correct_map = CorrectMap()
        expectedset = self.get_answers()
        for aid in self.answer_ids:	 # loop through IDs of <imageinput>
        #  fields in our stanza
            given = student_answers[aid]  # this should be a string of the form '[x,y]'
            correct_map.set(aid, 'incorrect')
            if not given:  # No answer to parse. Mark as incorrect and move on
                continue
            # parse given answer
            m = re.match('\[([0-9]+),([0-9]+)]', given.strip().replace(' ', ''))
            if not m:
                raise Exception('[capamodule.capa.responsetypes.imageinput] '
                                'error grading %s (input=%s)' % (aid, given))
            (gx, gy) = [int(x) for x in m.groups()]

            rectangles, regions = expectedset
            if rectangles[aid]:  # rectangles part - for backward compatibility
                # Check whether given point lies in any of the solution rectangles
                solution_rectangles = rectangles[aid].split(';')
                for solution_rectangle in solution_rectangles:
                    # parse expected answer
                    # TODO: Compile regexp on file load
                    m = re.match('[\(\[]([0-9]+),([0-9]+)[\)\]]-[\(\[]([0-9]+),([0-9]+)[\)\]]',
                                 solution_rectangle.strip().replace(' ', ''))
                    if not m:
                        msg = 'Error in problem specification! cannot parse rectangle in %s' % (
                            etree.tostring(self.ielements[aid], pretty_print=True))
                        raise Exception('[capamodule.capa.responsetypes.imageinput] ' + msg)
                    (llx, lly, urx, ury) = [int(x) for x in m.groups()]

                    # answer is correct if (x,y) is within the specified rectangle
                    if (llx <= gx <= urx) and (lly <= gy <= ury):
                        correct_map.set(aid, 'correct')
                        break
            if correct_map[aid]['correctness'] != 'correct' and regions[aid]:
                parsed_region = json.loads(regions[aid])
                if parsed_region:
                    if type(parsed_region[0][0]) != list:
                        # we have [[1,2],[3,4],[5,6]] - single region
                        # instead of [[[1,2],[3,4],[5,6], [[1,2],[3,4],[5,6]]]
                        # or [[[1,2],[3,4],[5,6]]] - multiple regions syntax
                        parsed_region = [parsed_region]
                    for region in parsed_region:
                        polygon = MultiPoint(region).convex_hull
                        if (polygon.type == 'Polygon' and
                                polygon.contains(Point(gx, gy))):
                            correct_map.set(aid, 'correct')
                            break
        return correct_map

    def get_answers(self):
        return (dict([(ie.get('id'), ie.get('rectangle')) for ie in self.ielements]),
                dict([(ie.get('id'), ie.get('regions')) for ie in self.ielements]))
#-----------------------------------------------------------------------------

class OpenEndedResponse(LoncapaResponse):
    """
    Grade student open ended responses using an external grading system,
    accessed through the xqueue system.

    Expects 'xqueue' dict in ModuleSystem with the following keys that are
    needed by OpenEndedResponse:

        system.xqueue = { 'interface': XqueueInterface object,
                          'callback_url': Per-StudentModule callback URL
                                          where results are posted (string),
                        }

    External requests are only submitted for student submission grading
        (i.e. and not for getting reference answers)

    By default, uses the OpenEndedResponse.DEFAULT_QUEUE queue.
    """

    DEFAULT_QUEUE = 'open-ended'
    DEFAULT_MESSAGE_QUEUE = 'open-ended-message'
    response_tag = 'openendedresponse'
    allowed_inputfields = ['openendedinput']
    max_inputfields = 1

    def setup_response(self):
        '''
        Configure OpenEndedResponse from XML.
        '''
        xml = self.xml
        self.url = xml.get('url', None)
        self.queue_name = xml.get('queuename', self.DEFAULT_QUEUE)
        self.message_queue_name = xml.get('message-queuename', self.DEFAULT_MESSAGE_QUEUE)

        # The openendedparam tag encapsulates all grader settings
        oeparam = self.xml.find('openendedparam')
        prompt = self.xml.find('prompt')
        rubric = self.xml.find('openendedrubric')

        #This is needed to attach feedback to specific responses later
        self.submission_id=None
        self.grader_id=None

        if oeparam is None:
            raise ValueError("No oeparam found in problem xml.")
        if prompt is None:
            raise ValueError("No prompt found in problem xml.")
        if rubric is None:
            raise ValueError("No rubric found in problem xml.")

        self._parse(oeparam, prompt, rubric)

    @staticmethod
    def stringify_children(node):
        """
        Modify code from stringify_children in xmodule.  Didn't import directly
        in order to avoid capa depending on xmodule (seems to be avoided in
        code)
        """
        parts=[node.text if node.text is not None else '']
        for p in node.getchildren():
            parts.append(etree.tostring(p, with_tail=True, encoding='unicode'))

        return ' '.join(parts)

    def _parse(self, oeparam, prompt, rubric):
        '''
        Parse OpenEndedResponse XML:
            self.initial_display
            self.payload - dict containing keys --
            'grader' : path to grader settings file, 'problem_id' : id of the problem

            self.answer - What to display when show answer is clicked
        '''
        # Note that OpenEndedResponse is agnostic to the specific contents of grader_payload
        prompt_string = self.stringify_children(prompt)
        rubric_string = self.stringify_children(rubric)

        grader_payload = oeparam.find('grader_payload')
        grader_payload = grader_payload.text if grader_payload is not None else ''

        #Update grader payload with student id.  If grader payload not json, error.
        try:
            parsed_grader_payload = json.loads(grader_payload)
            # NOTE: self.system.location is valid because the capa_module
            # __init__ adds it (easiest way to get problem location into
            # response types)
        except TypeError, ValueError:
            log.exception("Grader payload %r is not a json object!", grader_payload)
        parsed_grader_payload.update({
            'location' : self.system.location,
            'course_id' : self.system.course_id,
            'prompt' : prompt_string,
            'rubric' : rubric_string,
        })
        updated_grader_payload = json.dumps(parsed_grader_payload)

        self.payload = {'grader_payload': updated_grader_payload}

        self.initial_display = find_with_default(oeparam, 'initial_display', '')
        self.answer = find_with_default(oeparam, 'answer_display', 'No answer given.')
        try:
            self.max_score = int(find_with_default(oeparam, 'max_score', 1))
        except ValueError:
            self.max_score = 1

    def handle_message_post(self,event_info):
        """
        Handles a student message post (a reaction to the grade they received from an open ended grader type)
        Returns a boolean success/fail and an error message
        """
        survey_responses=event_info['survey_responses']
        for tag in ['feedback', 'submission_id', 'grader_id']:
            if tag not in survey_responses:
                return False, "Could not find needed tag {0}".format(tag)
        try:
            submission_id=int(survey_responses['submission_id'][0])
            grader_id = int(survey_responses['grader_id'][0])
            feedback = str(survey_responses['feedback'][0])
        except:
            error_message="Could not parse submission id, grader id, or feedback from message_post ajax call."
            log.exception(error_message)
            return False, error_message

        qinterface = self.system.xqueue['interface']
        qtime = datetime.strftime(datetime.now(), xqueue_interface.dateformat)
        anonymous_student_id = self.system.anonymous_student_id
        queuekey = xqueue_interface.make_hashkey(str(self.system.seed) + qtime +
                                                 anonymous_student_id +
                                                 self.answer_id)

        xheader = xqueue_interface.make_xheader(lms_key=queuekey,queue_name=self.message_queue_name)
        student_info = {'anonymous_student_id': anonymous_student_id,
                        'submission_time': qtime,
                        }
        contents= {
            'feedback' : feedback,
            'submission_id' : submission_id,
            'grader_id' : grader_id,
            'student_info' : json.dumps(student_info),
        }

        (error, msg) = qinterface.send_to_queue(header=xheader,
            body=json.dumps(contents))

        #Convert error to a success value
        success=True
        if error:
            success=False

        return success, "Successfully sent to queue."

    def get_score(self, student_answers):

        try:
            submission = student_answers[self.answer_id]
        except KeyError:
            msg = ('Cannot get student answer for answer_id: {0}. student_answers {1}'
                   .format(self.answer_id, student_answers))
            log.exception(msg)
            raise LoncapaProblemError(msg)

        # Prepare xqueue request
        #------------------------------------------------------------

        qinterface = self.system.xqueue['interface']
        qtime = datetime.strftime(datetime.now(), xqueue_interface.dateformat)

        anonymous_student_id = self.system.anonymous_student_id

        # Generate header
        queuekey = xqueue_interface.make_hashkey(str(self.system.seed) + qtime +
                                                 anonymous_student_id +
                                                 self.answer_id)

        xheader = xqueue_interface.make_xheader(lms_callback_url=self.system.xqueue['callback_url'],
            lms_key=queuekey,
            queue_name=self.queue_name)

        self.context.update({'submission': submission})

        contents = self.payload.copy()

        # Metadata related to the student submission revealed to the external grader
        student_info = {'anonymous_student_id': anonymous_student_id,
                        'submission_time': qtime,
                        }

        #Update contents with student response and student info
        contents.update({
            'student_info': json.dumps(student_info),
            'student_response': submission,
            'max_score' : self.max_score
            })

        # Submit request. When successful, 'msg' is the prior length of the queue
        (error, msg) = qinterface.send_to_queue(header=xheader,
            body=json.dumps(contents))

        # State associated with the queueing request
        queuestate = {'key': queuekey,
                      'time': qtime,}

        cmap = CorrectMap()
        if error:
            cmap.set(self.answer_id, queuestate=None,
                msg='Unable to deliver your submission to grader. (Reason: {0}.)'
                    ' Please try again later.'.format(msg))
        else:
            # Queueing mechanism flags:
            #   1) Backend: Non-null CorrectMap['queuestate'] indicates that
            #      the problem has been queued
            #   2) Frontend: correctness='incomplete' eventually trickles down
            #      through inputtypes.textbox and .filesubmission to inform the
            #      browser that the submission is queued (and it could e.g. poll)
            cmap.set(self.answer_id, queuestate=queuestate,
                     correctness='incomplete', msg=msg)

        return cmap

    def update_score(self, score_msg, oldcmap, queuekey):
        log.debug(score_msg)
        score_msg = self._parse_score_msg(score_msg)
        if not score_msg.valid:
            oldcmap.set(self.answer_id,
                msg = 'Invalid grader reply. Please contact the course staff.')
            return oldcmap

        correctness = 'correct' if score_msg.correct else 'incorrect'

        # TODO: Find out how this is used elsewhere, if any
        self.context['correct'] = correctness

        # Replace 'oldcmap' with new grading results if queuekey matches.  If queuekey
        # does not match, we keep waiting for the score_msg whose key actually matches
        if oldcmap.is_right_queuekey(self.answer_id, queuekey):
            # Sanity check on returned points
            points = score_msg.points
            if points < 0:
                points = 0

            # Queuestate is consumed, so reset it to None
            oldcmap.set(self.answer_id, npoints=points, correctness=correctness,
                msg = score_msg.msg.replace('&nbsp;', '&#160;'), queuestate=None)
        else:
            log.debug('OpenEndedResponse: queuekey {0} does not match for answer_id={1}.'.format(
                queuekey, self.answer_id))

        return oldcmap

    def get_answers(self):
        anshtml = '<span class="openended-answer"><pre><code>{0}</code></pre></span>'.format(self.answer)
        return {self.answer_id: anshtml}

    def get_initial_display(self):
        return {self.answer_id: self.initial_display}

    def _convert_longform_feedback_to_html(self, response_items):
        """
        Take in a dictionary, and return html strings for display to student.
        Input:
            response_items: Dictionary with keys success, feedback.
                if success is True, feedback should be a dictionary, with keys for
                   types of feedback, and the corresponding feedback values.
                if success is False, feedback is actually an error string.

                NOTE: this will need to change when we integrate peer grading, because
                that will have more complex feedback.

        Output:
            String -- html that can be displayed to the student.
        """

        # We want to display available feedback in a particular order.
        # This dictionary specifies which goes first--lower first.
        priorities = {# These go at the start of the feedback
                      'spelling': 0,
                      'grammar': 1,
                      # needs to be after all the other feedback
                      'markup_text': 3}

        default_priority = 2

        def get_priority(elt):
            """
            Args:
                elt: a tuple of feedback-type, feedback
            Returns:
                the priority for this feedback type
            """
            return priorities.get(elt[0], default_priority)

        def format_feedback(feedback_type, value):
            return """
            <div class="{feedback_type}">
            {value}
            </div>
            """.format(feedback_type=feedback_type, value=value)

        def format_feedback_hidden(feedback_type , value):
            return """
            <div class="{feedback_type}" style="display: none;">
            {value}
            </div>
            """.format(feedback_type=feedback_type, value=value)

        # TODO (vshnayder): design and document the details of this format so
        # that we can do proper escaping here (e.g. are the graders allowed to
        # include HTML?)

        for tag in ['success', 'feedback', 'submission_id', 'grader_id']:
            if tag not in response_items:
                return format_feedback('errors', 'Error getting feedback')

        feedback_items = response_items['feedback']
        try:
            feedback = json.loads(feedback_items)
        except (TypeError, ValueError):
            log.exception("feedback_items have invalid json %r", feedback_items)
            return format_feedback('errors', 'Could not parse feedback')

        if response_items['success']:
            if len(feedback) == 0:
                return format_feedback('errors', 'No feedback available')

            feedback_lst = sorted(feedback.items(), key=get_priority)
            feedback_list_part1 = u"\n".join(format_feedback(k, v) for k, v in feedback_lst)
        else:
            feedback_list_part1 = format_feedback('errors', response_items['feedback'])

        feedback_list_part2=u"\n".join([format_feedback_hidden(k,response_items[k]) for k in response_items.keys() if k in ['submission_id', 'grader_id']])
        return u"\n".join([feedback_list_part1,feedback_list_part2])

    def _format_feedback(self, response_items):
        """
        Input:
            Dictionary called feedback.  Must contain keys seen below.
        Output:
            Return error message or feedback template
        """

        feedback = self._convert_longform_feedback_to_html(response_items)

        if not response_items['success']:
            return self.system.render_template("open_ended_error.html",
                                               {'errors' : feedback})

        feedback_template = self.system.render_template("open_ended_feedback.html", {
            'grader_type': response_items['grader_type'],
            'score': response_items['score'],
            'feedback': feedback,
        })

        return feedback_template


    def _parse_score_msg(self, score_msg):
        """
         Grader reply is a JSON-dump of the following dict
           { 'correct': True/False,
             'score': Numeric value (floating point is okay) to assign to answer
             'msg': grader_msg
             'feedback' : feedback from grader
             }

        Returns (valid_score_msg, correct, score, msg):
            valid_score_msg: Flag indicating valid score_msg format (Boolean)
            correct:         Correctness of submission (Boolean)
            score:           Points to be assigned (numeric, can be float)
        """
        fail = ScoreMessage(valid=False, correct=False, points=0, msg='')
        try:
            score_result = json.loads(score_msg)
        except (TypeError, ValueError):
            log.error("External grader message should be a JSON-serialized dict."
                      " Received score_msg = {0}".format(score_msg))
            return fail

        if not isinstance(score_result, dict):
            log.error("External grader message should be a JSON-serialized dict."
                      " Received score_result = {0}".format(score_result))
            return fail

        for tag in ['score', 'feedback', 'grader_type', 'success', 'grader_id', 'submission_id']:
            if tag not in score_result:
                log.error("External grader message is missing required tag: {0}"
                          .format(tag))
                return fail

        feedback = self._format_feedback(score_result)
        self.submission_id=score_result['submission_id']
        self.grader_id=score_result['grader_id']

        # HACK: for now, just assume it's correct if you got more than 2/3.
        # Also assumes that score_result['score'] is an integer.
        score_ratio = int(score_result['score']) / self.max_score
        correct = (score_ratio >= 0.66)

        #Currently ignore msg and only return feedback (which takes the place of msg)
        return ScoreMessage(valid=True, correct=correct,
                            points=score_result['score'], msg=feedback)

#-----------------------------------------------------------------------------
# TEMPORARY: List of all response subclasses
# FIXME: To be replaced by auto-registration

__all__ = [CodeResponse,
           NumericalResponse,
           FormulaResponse,
           CustomResponse,
           SchematicResponse,
           ExternalResponse,
           ImageResponse,
           OptionResponse,
           SymbolicResponse,
           StringResponse,
           ChoiceResponse,
           MultipleChoiceResponse,
           TrueFalseResponse,
           JavascriptResponse,
           OpenEndedResponse]
