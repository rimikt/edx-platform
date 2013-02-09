import copy
from fs.errors import ResourceNotFoundError
import itertools
import json
import logging
from lxml import etree
from lxml.html import rewrite_links
from path import path
import os
import sys
import re

from pkg_resources import resource_string

from .capa_module import only_one, ComplexEncoder
from .editing_module import EditingDescriptor
from .html_checker import check_html
from progress import Progress
from .stringify import stringify_children
from .x_module import XModule
from .xml_module import XmlDescriptor
from xmodule.modulestore import Location
import self_assessment_module
import open_ended_module
from combined_open_ended_rubric import CombinedOpenEndedRubric, RubricParsingError, GRADER_TYPE_IMAGE_DICT, HUMAN_GRADER_TYPE
from .stringify import stringify_children
import dateutil
import dateutil.parser
import datetime
from timeparse import parse_timedelta

log = logging.getLogger("mitx.courseware")

# Set the default number of max attempts.  Should be 1 for production
# Set higher for debugging/testing
# attempts specified in xml definition overrides this.
MAX_ATTEMPTS = 10000

# Set maximum available number of points.
# Overriden by max_score specified in xml.
MAX_SCORE = 1

#The highest score allowed for the overall xmodule and for each rubric point
MAX_SCORE_ALLOWED = 3

#If true, default behavior is to score module as a practice problem.  Otherwise, no grade at all is shown in progress
#Metadata overrides this.
IS_SCORED = False

#If true, then default behavior is to require a file upload or pasted link from a student for this problem.
#Metadata overrides this.
ACCEPT_FILE_UPLOAD = False

#Contains all reasonable bool and case combinations of True
TRUE_DICT = ["True", True, "TRUE", "true"]

HUMAN_TASK_TYPE = {
    'selfassessment' : "Self Assessment",
    'openended' : "edX Assessment",
    }

class CombinedOpenEndedV1Module():
    """
    This is a module that encapsulates all open ended grading (self assessment, peer assessment, etc).
    It transitions between problems, and support arbitrary ordering.
    Each combined open ended module contains one or multiple "child" modules.
    Child modules track their own state, and can transition between states.  They also implement get_html and
    handle_ajax.
    The combined open ended module transitions between child modules as appropriate, tracks its own state, and passess
    ajax requests from the browser to the child module or handles them itself (in the cases of reset and next problem)
    ajax actions implemented by all children are:
        'save_answer' -- Saves the student answer
        'save_assessment' -- Saves the student assessment (or external grader assessment)
        'save_post_assessment' -- saves a post assessment (hint, feedback on feedback, etc)
    ajax actions implemented by combined open ended module are:
        'reset' -- resets the whole combined open ended module and returns to the first child module
        'next_problem' -- moves to the next child module
        'get_results' -- gets results from a given child module

    Types of children. Task is synonymous with child module, so each combined open ended module
    incorporates multiple children (tasks):
        openendedmodule
        selfassessmentmodule
    """
    STATE_VERSION = 1

    # states
    INITIAL = 'initial'
    ASSESSING = 'assessing'
    INTERMEDIATE_DONE = 'intermediate_done'
    DONE = 'done'

    js = {'coffee': [resource_string(__name__, 'js/src/combinedopenended/display.coffee'),
                     resource_string(__name__, 'js/src/collapsible.coffee'),
                     resource_string(__name__, 'js/src/javascript_loader.coffee'),
                     ]}
    js_module_name = "CombinedOpenEnded"

    css = {'scss': [resource_string(__name__, 'css/combinedopenended/display.scss')]}

    def __init__(self, system, location, definition, descriptor,
                 instance_state=None, shared_state=None, metadata = None, static_data = None, **kwargs):

        """
        Definition file should have one or many task blocks, a rubric block, and a prompt block:

        Sample file:
        <combinedopenended attempts="10000" max_score="1">
            <rubric>
                Blah blah rubric.
            </rubric>
            <prompt>
                Some prompt.
            </prompt>
            <task>
                <selfassessment>
                    <hintprompt>
                        What hint about this problem would you give to someone?
                    </hintprompt>
                    <submitmessage>
                        Save Succcesful.  Thanks for participating!
                    </submitmessage>
                </selfassessment>
            </task>
            <task>
                <openended min_score_to_attempt="1" max_score_to_attempt="1">
                        <openendedparam>
                            <initial_display>Enter essay here.</initial_display>
                            <answer_display>This is the answer.</answer_display>
                            <grader_payload>{"grader_settings" : "ml_grading.conf",
                            "problem_id" : "6.002x/Welcome/OETest"}</grader_payload>
                        </openendedparam>
                </openended>
            </task>
        </combinedopenended>

        """

        self.metadata = metadata
        self.display_name = metadata.get('display_name', "Open Ended")
        self.rewrite_content_links = static_data.get('rewrite_content_links',"")


        # Load instance state
        if instance_state is not None:
            instance_state = json.loads(instance_state)
        else:
            instance_state = {}

        #We need to set the location here so the child modules can use it
        system.set('location', location)
        self.system = system

        #Tells the system which xml definition to load
        self.current_task_number = instance_state.get('current_task_number', 0)
        #This loads the states of the individual children
        self.task_states = instance_state.get('task_states', [])
        #Overall state of the combined open ended module
        self.state = instance_state.get('state', self.INITIAL)

        self.attempts = instance_state.get('attempts', 0)

        #Allow reset is true if student has failed the criteria to move to the next child task
        self.allow_reset = instance_state.get('ready_to_reset', False)
        self.max_attempts = int(self.metadata.get('attempts', MAX_ATTEMPTS))
        self.is_scored = self.metadata.get('is_graded', IS_SCORED) in TRUE_DICT
        self.accept_file_upload = self.metadata.get('accept_file_upload', ACCEPT_FILE_UPLOAD) in TRUE_DICT

        display_due_date_string = self.metadata.get('due', None)
        if display_due_date_string is not None:
            try:
                self.display_due_date = dateutil.parser.parse(display_due_date_string)
            except ValueError:
                log.error("Could not parse due date {0} for location {1}".format(display_due_date_string, location))
                raise
        else:
            self.display_due_date = None

        grace_period_string = self.metadata.get('graceperiod', None)
        if grace_period_string is not None and self.display_due_date:
            try:
                self.grace_period = parse_timedelta(grace_period_string)
                self.close_date = self.display_due_date + self.grace_period
            except:
                log.error("Error parsing the grace period {0} for location {1}".format(grace_period_string, location))
                raise
        else:
            self.grace_period = None
            self.close_date = self.display_due_date

        # Used for progress / grading.  Currently get credit just for
        # completion (doesn't matter if you self-assessed correct/incorrect).
        self._max_score = int(self.metadata.get('max_score', MAX_SCORE))

        self.rubric_renderer = CombinedOpenEndedRubric(system, True)
        rubric_string = stringify_children(definition['rubric'])
        self.rubric_renderer.check_if_rubric_is_parseable(rubric_string, location, MAX_SCORE_ALLOWED, self._max_score)

        #Static data is passed to the child modules to render
        self.static_data = {
            'max_score': self._max_score,
            'max_attempts': self.max_attempts,
            'prompt': definition['prompt'],
            'rubric': definition['rubric'],
            'display_name': self.display_name,
            'accept_file_upload': self.accept_file_upload,
            'close_date' : self.close_date,
            }

        self.task_xml = definition['task_xml']
        self.location = location
        self.setup_next_task()

    def get_tag_name(self, xml):
        """
        Gets the tag name of a given xml block.
        Input: XML string
        Output: The name of the root tag
        """
        tag = etree.fromstring(xml).tag
        return tag

    def overwrite_state(self, current_task_state):
        """
        Overwrites an instance state and sets the latest response to the current response.  This is used
        to ensure that the student response is carried over from the first child to the rest.
        Input: Task state json string
        Output: Task state json string
        """
        last_response_data = self.get_last_response(self.current_task_number - 1)
        last_response = last_response_data['response']

        loaded_task_state = json.loads(current_task_state)
        if loaded_task_state['state'] == self.INITIAL:
            loaded_task_state['state'] = self.ASSESSING
            loaded_task_state['created'] = True
            loaded_task_state['history'].append({'answer': last_response})
            current_task_state = json.dumps(loaded_task_state)
        return current_task_state

    def child_modules(self):
        """
        Returns the constructors associated with the child modules in a dictionary.  This makes writing functions
        simpler (saves code duplication)
        Input: None
        Output: A dictionary of dictionaries containing the descriptor functions and module functions
        """
        child_modules = {
            'openended': open_ended_module.OpenEndedModule,
            'selfassessment': self_assessment_module.SelfAssessmentModule,
            }
        child_descriptors = {
            'openended': open_ended_module.OpenEndedDescriptor,
            'selfassessment': self_assessment_module.SelfAssessmentDescriptor,
            }
        children = {
            'modules': child_modules,
            'descriptors': child_descriptors,
            }
        return children

    def setup_next_task(self, reset=False):
        """
        Sets up the next task for the module.  Creates an instance state if none exists, carries over the answer
        from the last instance state to the next if needed.
        Input: A boolean indicating whether or not the reset function is calling.
        Output: Boolean True (not useful right now)
        """
        current_task_state = None
        if len(self.task_states) > self.current_task_number:
            current_task_state = self.task_states[self.current_task_number]

        self.current_task_xml = self.task_xml[self.current_task_number]

        if self.current_task_number > 0:
            self.allow_reset = self.check_allow_reset()
            if self.allow_reset:
                self.current_task_number = self.current_task_number - 1

        current_task_type = self.get_tag_name(self.current_task_xml)

        children = self.child_modules()
        child_task_module = children['modules'][current_task_type]

        self.current_task_descriptor = children['descriptors'][current_task_type](self.system)

        #This is the xml object created from the xml definition of the current task
        etree_xml = etree.fromstring(self.current_task_xml)

        #This sends the etree_xml object through the descriptor module of the current task, and
        #returns the xml parsed by the descriptor
        self.current_task_parsed_xml = self.current_task_descriptor.definition_from_xml(etree_xml, self.system)
        if current_task_state is None and self.current_task_number == 0:
            self.current_task = child_task_module(self.system, self.location,
                self.current_task_parsed_xml, self.current_task_descriptor, self.static_data)
            self.task_states.append(self.current_task.get_instance_state())
            self.state = self.ASSESSING
        elif current_task_state is None and self.current_task_number > 0:
            last_response_data = self.get_last_response(self.current_task_number - 1)
            last_response = last_response_data['response']
            current_task_state = json.dumps({
                'state': self.ASSESSING,
                'version': self.STATE_VERSION,
                'max_score': self._max_score,
                'attempts': 0,
                'created': True,
                'history': [{'answer': last_response}],
                })
            self.current_task = child_task_module(self.system, self.location,
                self.current_task_parsed_xml, self.current_task_descriptor, self.static_data,
                instance_state=current_task_state)
            self.task_states.append(self.current_task.get_instance_state())
            self.state = self.ASSESSING
        else:
            if self.current_task_number > 0 and not reset:
                current_task_state = self.overwrite_state(current_task_state)
            self.current_task = child_task_module(self.system, self.location,
                self.current_task_parsed_xml, self.current_task_descriptor, self.static_data,
                instance_state=current_task_state)

        return True

    def check_allow_reset(self):
        """
        Checks to see if the student has passed the criteria to move to the next module.  If not, sets
        allow_reset to true and halts the student progress through the tasks.
        Input: None
        Output: the allow_reset attribute of the current module.
        """
        if not self.allow_reset:
            if self.current_task_number > 0:
                last_response_data = self.get_last_response(self.current_task_number - 1)
                current_response_data = self.get_current_attributes(self.current_task_number)

                if(current_response_data['min_score_to_attempt'] > last_response_data['score']
                   or current_response_data['max_score_to_attempt'] < last_response_data['score']):
                    self.state = self.DONE
                    self.allow_reset = True

        return self.allow_reset

    def get_context(self):
        """
        Generates a context dictionary that is used to render html.
        Input: None
        Output: A dictionary that can be rendered into the combined open ended template.
        """
        task_html = self.get_html_base()
        #set context variables and render template

        context = {
            'items': [{'content': task_html}],
            'ajax_url': self.system.ajax_url,
            'allow_reset': self.allow_reset,
            'state': self.state,
            'task_count': len(self.task_xml),
            'task_number': self.current_task_number + 1,
            'status': self.get_status(),
            'display_name': self.display_name,
            'accept_file_upload': self.accept_file_upload,
            }

        return context

    def get_html(self):
        """
        Gets HTML for rendering.
        Input: None
        Output: rendered html
        """
        context = self.get_context()
        html = self.system.render_template('combined_open_ended.html', context)
        return html

    def get_html_nonsystem(self):
        """
        Gets HTML for rendering via AJAX.  Does not use system, because system contains some additional
        html, which is not appropriate for returning via ajax calls.
        Input: None
        Output: HTML rendered directly via Mako
        """
        context = self.get_context()
        html = self.system.render_template('combined_open_ended.html', context)
        return html

    def get_html_base(self):
        """
        Gets the HTML associated with the current child task
        Input: None
        Output: Child task HTML
        """
        self.update_task_states()
        html = self.current_task.get_html(self.system)
        return_html = rewrite_links(html, self.rewrite_content_links)
        return return_html

    def get_current_attributes(self, task_number):
        """
        Gets the min and max score to attempt attributes of the specified task.
        Input: The number of the task.
        Output: The minimum and maximum scores needed to move on to the specified task.
        """
        task_xml = self.task_xml[task_number]
        etree_xml = etree.fromstring(task_xml)
        min_score_to_attempt = int(etree_xml.attrib.get('min_score_to_attempt', 0))
        max_score_to_attempt = int(etree_xml.attrib.get('max_score_to_attempt', self._max_score))
        return {'min_score_to_attempt': min_score_to_attempt, 'max_score_to_attempt': max_score_to_attempt}

    def get_last_response(self, task_number):
        """
        Returns data associated with the specified task number, such as the last response, score, etc.
        Input: The number of the task.
        Output: A dictionary that contains information about the specified task.
        """
        last_response = ""
        task_state = self.task_states[task_number]
        task_xml = self.task_xml[task_number]
        task_type = self.get_tag_name(task_xml)

        children = self.child_modules()

        task_descriptor = children['descriptors'][task_type](self.system)
        etree_xml = etree.fromstring(task_xml)

        min_score_to_attempt = int(etree_xml.attrib.get('min_score_to_attempt', 0))
        max_score_to_attempt = int(etree_xml.attrib.get('max_score_to_attempt', self._max_score))

        task_parsed_xml = task_descriptor.definition_from_xml(etree_xml, self.system)
        task = children['modules'][task_type](self.system, self.location, task_parsed_xml, task_descriptor,
            self.static_data, instance_state=task_state)
        last_response = task.latest_answer()
        last_score = task.latest_score()
        last_post_assessment = task.latest_post_assessment(self.system)
        last_post_feedback = ""
        if task_type == "openended":
            last_post_assessment = task.latest_post_assessment(self.system, short_feedback=False, join_feedback=False)
            if isinstance(last_post_assessment, list):
                eval_list = []
                for i in xrange(0, len(last_post_assessment)):
                    eval_list.append(task.format_feedback_with_evaluation(self.system, last_post_assessment[i]))
                last_post_evaluation = "".join(eval_list)
            else:
                last_post_evaluation = task.format_feedback_with_evaluation(self.system, last_post_assessment)
            last_post_assessment = last_post_evaluation
            rubric_data = task._parse_score_msg(task.history[-1].get('post_assessment', ""), self.system)
            rubric_scores = rubric_data['rubric_scores']
            grader_types = rubric_data['grader_types']
            feedback_items = rubric_data['feedback_items']
        elif task_type== "selfassessment":
            rubric_scores = last_post_assessment
            grader_types = ['SA']
            feedback_items = ['']
            last_post_assessment = ""
        last_correctness = task.is_last_response_correct()
        max_score = task.max_score()
        state = task.state
        if task_type in HUMAN_TASK_TYPE:
            human_task_name = HUMAN_TASK_TYPE[task_type]
        else:
            human_task_name = task_type

        if state in task.HUMAN_NAMES:
            human_state = task.HUMAN_NAMES[state]
        else:
            human_state = state
        if len(grader_types)>0:
            grader_type = grader_types[0]
        else:
            grader_type = "IN"

        if grader_type in HUMAN_GRADER_TYPE:
            human_grader_name = HUMAN_GRADER_TYPE[grader_type]
        else:
            human_grader_name = grader_type

        last_response_dict = {
            'response': last_response,
            'score': last_score,
            'post_assessment': last_post_assessment,
            'type': task_type,
            'max_score': max_score,
            'state': state,
            'human_state': human_state,
            'human_task': human_task_name,
            'correct': last_correctness,
            'min_score_to_attempt': min_score_to_attempt,
            'max_score_to_attempt': max_score_to_attempt,
            'rubric_scores' : rubric_scores,
            'grader_types' : grader_types,
            'feedback_items' : feedback_items,
            'grader_type' : grader_type,
            'human_grader_type' : human_grader_name,
            }
        return last_response_dict

    def update_task_states(self):
        """
        Updates the task state of the combined open ended module with the task state of the current child module.
        Input: None
        Output: boolean indicating whether or not the task state changed.
        """
        changed = False
        if not self.allow_reset:
            self.task_states[self.current_task_number] = self.current_task.get_instance_state()
            current_task_state = json.loads(self.task_states[self.current_task_number])
            if current_task_state['state'] == self.DONE:
                self.current_task_number += 1
                if self.current_task_number >= (len(self.task_xml)):
                    self.state = self.DONE
                    self.current_task_number = len(self.task_xml) - 1
                else:
                    self.state = self.INITIAL
                changed = True
                self.setup_next_task()
        return changed

    def update_task_states_ajax(self, return_html):
        """
        Runs the update task states function for ajax calls.  Currently the same as update_task_states
        Input: The html returned by the handle_ajax function of the child
        Output: New html that should be rendered
        """
        changed = self.update_task_states()
        if changed:
            #return_html=self.get_html()
            pass
        return return_html

    def get_rubric(self, get):
        """
        Gets the results of a given grader via ajax.
        Input: AJAX get dictionary
        Output: Dictionary to be rendered via ajax that contains the result html.
        """
        all_responses = []
        loop_up_to_task = self.current_task_number+1
        if self.state in [self.ASSESSING, self.INITIAL] and self.current_task_number>0:
            loop_up_to_task = loop_up_to_task-1
        log.debug(self.allow_reset)
        log.debug(self.check_allow_reset())
        log.debug(self.state)
        log.debug(self.current_task_number)
        log.debug(loop_up_to_task)
        for i in xrange(0,loop_up_to_task):
            all_responses.append(self.get_last_response(i))
        rubric_scores = [rd['rubric_scores'] for rd in all_responses if len(rd['rubric_scores'])>0]
        grader_types = [rd['grader_types'] for rd in all_responses if len(rd['grader_types'])>0]
        feedback_items = [rd['feedback_items'] for rd in all_responses if len(rd['feedback_items'])>0]
        log.debug(rubric_scores)
        log.debug(grader_types)
        log.debug(feedback_items)
        rubric_html = self.rubric_renderer.render_combined_rubric(stringify_children(self.static_data['rubric']), rubric_scores,
            grader_types, feedback_items)

        response_dict = all_responses[-1]
        context = {
            'results': rubric_html,
            'task_name' : 'Combined Rubric',
            'class_name' : 'combined-rubric-container'
        }
        html = self.system.render_template('combined_open_ended_results.html', context)
        return {'html': html, 'success': True}

    def get_results(self, get):
        """
        Gets the results of a given grader via ajax.
        Input: AJAX get dictionary
        Output: Dictionary to be rendered via ajax that contains the result html.
        """
        task_number = int(get['task_number'])
        self.update_task_states()
        response_dict = self.get_last_response(task_number)
        context = {
            'results': response_dict['post_assessment'],
            'task_number': task_number + 1,
            'task_name' : response_dict['human_task'],
            'class_name' : "result-container",
        }
        html = self.system.render_template('combined_open_ended_results.html', context)
        return {'html': html, 'success': True}

    def get_status_ajax(self, get):
        """
        Gets the results of a given grader via ajax.
        Input: AJAX get dictionary
        Output: Dictionary to be rendered via ajax that contains the result html.
        """
        html = self.get_status()
        return {'html': html, 'success': True}

    def handle_ajax(self, dispatch, get):
        """
        This is called by courseware.module_render, to handle an AJAX call.
        "get" is request.POST.

        Returns a json dictionary:
        { 'progress_changed' : True/False,
        'progress': 'none'/'in_progress'/'done',
        <other request-specific values here > }
        """

        handlers = {
            'next_problem': self.next_problem,
            'reset': self.reset,
            'get_results': self.get_results,
            'get_combined_rubric': self.get_rubric,
            'get_status' : self.get_status_ajax,
        }

        if dispatch not in handlers:
            return_html = self.current_task.handle_ajax(dispatch, get, self.system)
            return self.update_task_states_ajax(return_html)

        d = handlers[dispatch](get)
        return json.dumps(d, cls=ComplexEncoder)

    def next_problem(self, get):
        """
        Called via ajax to advance to the next problem.
        Input: AJAX get request.
        Output: Dictionary to be rendered
        """
        self.update_task_states()
        return {'success': True, 'html': self.get_html_nonsystem(), 'allow_reset': self.allow_reset}

    def reset(self, get):
        """
        If resetting is allowed, reset the state of the combined open ended module.
        Input: AJAX get dictionary
        Output: AJAX dictionary to tbe rendered
        """
        if self.state != self.DONE:
            if not self.allow_reset:
                return self.out_of_sync_error(get)

        if self.attempts > self.max_attempts:
            return {
                'success': False,
                'error': 'Too many attempts.'
            }
        self.state = self.INITIAL
        self.allow_reset = False
        for i in xrange(0, len(self.task_xml)):
            self.current_task_number = i
            self.setup_next_task(reset=True)
            self.current_task.reset(self.system)
            self.task_states[self.current_task_number] = self.current_task.get_instance_state()
        self.current_task_number = 0
        self.allow_reset = False
        self.setup_next_task()
        return {'success': True, 'html': self.get_html_nonsystem()}

    def get_instance_state(self):
        """
        Returns the current instance state.  The module can be recreated from the instance state.
        Input: None
        Output: A dictionary containing the instance state.
        """

        state = {
            'version': self.STATE_VERSION,
            'current_task_number': self.current_task_number,
            'state': self.state,
            'task_states': self.task_states,
            'attempts': self.attempts,
            'ready_to_reset': self.allow_reset,
            }

        return json.dumps(state)

    def get_status(self):
        """
        Gets the status panel to be displayed at the top right.
        Input: None
        Output: The status html to be rendered
        """
        status = []
        for i in xrange(0, self.current_task_number + 1):
            task_data = self.get_last_response(i)
            task_data.update({'task_number': i + 1})
            status.append(task_data)

        context = {'status_list': status, 'grader_type_image_dict' : GRADER_TYPE_IMAGE_DICT}
        status_html = self.system.render_template("combined_open_ended_status.html", context)

        return status_html

    def check_if_done_and_scored(self):
        """
        Checks if the object is currently in a finished state (either student didn't meet criteria to move
        to next step, in which case they are in the allow_reset state, or they are done with the question
        entirely, in which case they will be in the self.DONE state), and if it is scored or not.
        @return: Boolean corresponding to the above.
        """
        return (self.state == self.DONE or self.allow_reset) and self.is_scored

    def get_score(self):
        """
        Score the student received on the problem, or None if there is no
        score.

        Returns:
          dictionary
             {'score': integer, from 0 to get_max_score(),
              'total': get_max_score()}
        """
        max_score = None
        score = None
        if self.check_if_done_and_scored():
            last_response = self.get_last_response(self.current_task_number)
            max_score = last_response['max_score']
            score = last_response['score']

        score_dict = {
            'score': score,
            'total': max_score,
            }

        return score_dict

    def max_score(self):
        ''' Maximum score. Two notes:

            * This is generic; in abstract, a problem could be 3/5 points on one
              randomization, and 5/7 on another
        '''
        max_score = None
        if self.check_if_done_and_scored():
            last_response = self.get_last_response(self.current_task_number)
            max_score = last_response['max_score']
        return max_score

    def get_progress(self):
        ''' Return a progress.Progress object that represents how far the
        student has gone in this module.  Must be implemented to get correct
        progress tracking behavior in nesting modules like sequence and
        vertical.

        If this module has no notion of progress, return None.
        '''
        progress_object = Progress(self.current_task_number, len(self.task_xml))

        return progress_object


class CombinedOpenEndedV1Descriptor(XmlDescriptor, EditingDescriptor):
    """
    Module for adding combined open ended questions
    """
    mako_template = "widgets/html-edit.html"
    module_class = CombinedOpenEndedV1Module
    filename_extension = "xml"

    stores_state = True
    has_score = True
    template_dir_name = "combinedopenended"

    js = {'coffee': [resource_string(__name__, 'js/src/html/edit.coffee')]}
    js_module_name = "HTMLEditingDescriptor"

    @classmethod
    def definition_from_xml(cls, xml_object, system):
        """
        Pull out the individual tasks, the rubric, and the prompt, and parse

        Returns:
        {
        'rubric': 'some-html',
        'prompt': 'some-html',
        'task_xml': dictionary of xml strings,
        }
        """
        expected_children = ['task', 'rubric', 'prompt']
        for child in expected_children:
            if len(xml_object.xpath(child)) == 0:
                raise ValueError("Combined Open Ended definition must include at least one '{0}' tag".format(child))

        def parse_task(k):
            """Assumes that xml_object has child k"""
            return [stringify_children(xml_object.xpath(k)[i]) for i in xrange(0, len(xml_object.xpath(k)))]

        def parse(k):
            """Assumes that xml_object has child k"""
            return xml_object.xpath(k)[0]

        return {'task_xml': parse_task('task'), 'prompt': parse('prompt'), 'rubric': parse('rubric')}


    def definition_to_xml(self, resource_fs):
        '''Return an xml element representing this definition.'''
        elt = etree.Element('combinedopenended')

        def add_child(k):
            child_str = '<{tag}>{body}</{tag}>'.format(tag=k, body=self.definition[k])
            child_node = etree.fromstring(child_str)
            elt.append(child_node)

        for child in ['task']:
            add_child(child)

        return elt