import json
from mock import Mock, MagicMock, ANY
import unittest

from xmodule.open_ended_grading_classes.openendedchild import OpenEndedChild
from xmodule.open_ended_grading_classes.open_ended_module import OpenEndedModule
from xmodule.open_ended_grading_classes.combined_open_ended_modulev1 import CombinedOpenEndedV1Module
from xmodule.combined_open_ended_module import CombinedOpenEndedModule

from xmodule.modulestore import Location
from lxml import etree
import capa.xqueue_interface as xqueue_interface
from datetime import datetime
import logging

log = logging.getLogger(__name__)

from . import test_system

import test_util_open_ended

"""
Tests for the various pieces of the CombinedOpenEndedGrading system

OpenEndedChild
OpenEndedModule

"""


class OpenEndedChildTest(unittest.TestCase):
    location = Location(["i4x", "edX", "sa_test", "selfassessment",
                         "SampleQuestion"])

    metadata = json.dumps({'attempts': '10'})
    prompt = etree.XML("<prompt>This is a question prompt</prompt>")
    rubric = '''<rubric><rubric>
        <category>
        <description>Response Quality</description>
        <option>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option>
        <option>Second option</option>
        </category>
         </rubric></rubric>'''
    max_score = 1

    static_data = {
        'max_attempts': 20,
        'prompt': prompt,
        'rubric': rubric,
        'max_score': max_score,
        'display_name': 'Name',
        'accept_file_upload': False,
        'close_date': None,
        's3_interface': "",
        'open_ended_grading_interface': {},
        'skip_basic_checks': False,
    }
    definition = Mock()
    descriptor = Mock()

    def setUp(self):
        self.test_system = test_system()
        self.openendedchild = OpenEndedChild(self.test_system, self.location,
                                             self.definition, self.descriptor, self.static_data, self.metadata)


    def test_latest_answer_empty(self):
        answer = self.openendedchild.latest_answer()
        self.assertEqual(answer, "")

    def test_latest_score_empty(self):
        answer = self.openendedchild.latest_score()
        self.assertEqual(answer, None)

    def test_latest_post_assessment_empty(self):
        answer = self.openendedchild.latest_post_assessment(self.test_system)
        self.assertEqual(answer, "")

    def test_new_history_entry(self):
        new_answer = "New Answer"
        self.openendedchild.new_history_entry(new_answer)
        answer = self.openendedchild.latest_answer()
        self.assertEqual(answer, new_answer)

        new_answer = "Newer Answer"
        self.openendedchild.new_history_entry(new_answer)
        answer = self.openendedchild.latest_answer()
        self.assertEqual(new_answer, answer)

    def test_record_latest_score(self):
        new_answer = "New Answer"
        self.openendedchild.new_history_entry(new_answer)
        new_score = 3
        self.openendedchild.record_latest_score(new_score)
        score = self.openendedchild.latest_score()
        self.assertEqual(score, 3)

        new_score = 4
        self.openendedchild.new_history_entry(new_answer)
        self.openendedchild.record_latest_score(new_score)
        score = self.openendedchild.latest_score()
        self.assertEqual(score, 4)

    def test_record_latest_post_assessment(self):
        new_answer = "New Answer"
        self.openendedchild.new_history_entry(new_answer)

        post_assessment = "Post assessment"
        self.openendedchild.record_latest_post_assessment(post_assessment)
        self.assertEqual(post_assessment,
                         self.openendedchild.latest_post_assessment(self.test_system))

    def test_get_score(self):
        new_answer = "New Answer"
        self.openendedchild.new_history_entry(new_answer)

        score = self.openendedchild.get_score()
        self.assertEqual(score['score'], 0)
        self.assertEqual(score['total'], self.static_data['max_score'])

        new_score = 4
        self.openendedchild.new_history_entry(new_answer)
        self.openendedchild.record_latest_score(new_score)
        score = self.openendedchild.get_score()
        self.assertEqual(score['score'], new_score)
        self.assertEqual(score['total'], self.static_data['max_score'])

    def test_reset(self):
        self.openendedchild.reset(self.test_system)
        state = json.loads(self.openendedchild.get_instance_state())
        self.assertEqual(state['child_state'], OpenEndedChild.INITIAL)

    def test_is_last_response_correct(self):
        new_answer = "New Answer"
        self.openendedchild.new_history_entry(new_answer)
        self.openendedchild.record_latest_score(self.static_data['max_score'])
        self.assertEqual(self.openendedchild.is_last_response_correct(),
                         'correct')

        self.openendedchild.new_history_entry(new_answer)
        self.openendedchild.record_latest_score(0)
        self.assertEqual(self.openendedchild.is_last_response_correct(),
                         'incorrect')


class OpenEndedModuleTest(unittest.TestCase):
    location = Location(["i4x", "edX", "sa_test", "selfassessment",
                         "SampleQuestion"])

    metadata = json.dumps({'attempts': '10'})
    prompt = etree.XML("<prompt>This is a question prompt</prompt>")
    rubric = etree.XML('''<rubric>
        <category>
        <description>Response Quality</description>
        <option>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option>
        </category>
         </rubric>''')
    max_score = 4

    static_data = {
        'max_attempts': 20,
        'prompt': prompt,
        'rubric': rubric,
        'max_score': max_score,
        'display_name': 'Name',
        'accept_file_upload': False,
        'rewrite_content_links': "",
        'close_date': None,
        's3_interface': test_util_open_ended.S3_INTERFACE,
        'open_ended_grading_interface': test_util_open_ended.OPEN_ENDED_GRADING_INTERFACE,
        'skip_basic_checks': False,
    }

    oeparam = etree.XML('''
      <openendedparam>
            <initial_display>Enter essay here.</initial_display>
            <answer_display>This is the answer.</answer_display>
            <grader_payload>{"grader_settings" : "ml_grading.conf", "problem_id" : "6.002x/Welcome/OETest"}</grader_payload>
        </openendedparam>
    ''')
    definition = {'oeparam': oeparam}
    descriptor = Mock()

    def setUp(self):
        self.test_system = test_system()

        self.test_system.location = self.location
        self.mock_xqueue = MagicMock()
        self.mock_xqueue.send_to_queue.return_value = (None, "Message")

        def constructed_callback(dispatch="score_update"):
            return dispatch

        self.test_system.xqueue = {'interface': self.mock_xqueue, 'construct_callback': constructed_callback,
                                   'default_queuename': 'testqueue',
                                   'waittime': 1}
        self.openendedmodule = OpenEndedModule(self.test_system, self.location,
                                               self.definition, self.descriptor, self.static_data, self.metadata)

    def test_message_post(self):
        get = {'feedback': 'feedback text',
               'submission_id': '1',
               'grader_id': '1',
               'score': 3}
        qtime = datetime.strftime(datetime.now(), xqueue_interface.dateformat)
        student_info = {'anonymous_student_id': self.test_system.anonymous_student_id,
                        'submission_time': qtime}
        contents = {
            'feedback': get['feedback'],
            'submission_id': int(get['submission_id']),
            'grader_id': int(get['grader_id']),
            'score': get['score'],
            'student_info': json.dumps(student_info)
        }

        result = self.openendedmodule.message_post(get, self.test_system)
        self.assertTrue(result['success'])
        # make sure it's actually sending something we want to the queue
        self.mock_xqueue.send_to_queue.assert_called_with(body=json.dumps(contents), header=ANY)

        state = json.loads(self.openendedmodule.get_instance_state())
        self.assertIsNotNone(state['child_state'], OpenEndedModule.DONE)

    def test_send_to_grader(self):
        submission = "This is a student submission"
        qtime = datetime.strftime(datetime.now(), xqueue_interface.dateformat)
        student_info = {'anonymous_student_id': self.test_system.anonymous_student_id,
                        'submission_time': qtime}
        contents = self.openendedmodule.payload.copy()
        contents.update({
            'student_info': json.dumps(student_info),
            'student_response': submission,
            'max_score': self.max_score
        })
        result = self.openendedmodule.send_to_grader(submission, self.test_system)
        self.assertTrue(result)
        self.mock_xqueue.send_to_queue.assert_called_with(body=json.dumps(contents), header=ANY)

    def update_score_single(self):
        self.openendedmodule.new_history_entry("New Entry")
        score_msg = {
            'correct': True,
            'score': 4,
            'msg': 'Grader Message',
            'feedback': "Grader Feedback"
        }
        get = {'queuekey': "abcd",
               'xqueue_body': score_msg}
        self.openendedmodule.update_score(get, self.test_system)

    def update_score_single(self):
        self.openendedmodule.new_history_entry("New Entry")
        feedback = {
            "success": True,
            "feedback": "Grader Feedback"
        }
        score_msg = {
            'correct': True,
            'score': 4,
            'msg': 'Grader Message',
            'feedback': json.dumps(feedback),
            'grader_type': 'IN',
            'grader_id': '1',
            'submission_id': '1',
            'success': True,
            'rubric_scores': [0],
            'rubric_scores_complete': True,
            'rubric_xml': etree.tostring(self.rubric)
        }
        get = {'queuekey': "abcd",
               'xqueue_body': json.dumps(score_msg)}
        self.openendedmodule.update_score(get, self.test_system)

    def test_latest_post_assessment(self):
        self.update_score_single()
        assessment = self.openendedmodule.latest_post_assessment(self.test_system)
        self.assertFalse(assessment == '')
        # check for errors
        self.assertFalse('errors' in assessment)

    def test_update_score(self):
        self.update_score_single()
        score = self.openendedmodule.latest_score()
        self.assertEqual(score, 4)


class CombinedOpenEndedModuleTest(unittest.TestCase):
    location = Location(["i4x", "edX", "open_ended", "combinedopenended",
                         "SampleQuestion"])
    definition_template = """
                    <combinedopenended attempts="10000">
                    {rubric}
                    {prompt}
                    <task>
                    {task1}
                    </task>
                    <task>
                    {task2}
                    </task>
                    </combinedopenended>
                    """
    prompt = "<prompt>This is a question prompt</prompt>"
    rubric = '''<rubric><rubric>
        <category>
        <description>Response Quality</description>
        <option>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option>
        <option>Second option</option>
        </category>
         </rubric></rubric>'''
    max_score = 1

    metadata = {'attempts': '10', 'max_score': max_score}

    static_data = {
        'max_attempts': 20,
        'prompt': prompt,
        'rubric': rubric,
        'max_score': max_score,
        'display_name': 'Name',
        'accept_file_upload': False,
        'rewrite_content_links': "",
        'close_date': "",
        's3_interface': test_util_open_ended.S3_INTERFACE,
        'open_ended_grading_interface': test_util_open_ended.OPEN_ENDED_GRADING_INTERFACE,
        'skip_basic_checks': False,
        'is_graded': True,
    }

    oeparam = etree.XML('''
      <openendedparam>
            <initial_display>Enter essay here.</initial_display>
            <answer_display>This is the answer.</answer_display>
            <grader_payload>{"grader_settings" : "ml_grading.conf", "problem_id" : "6.002x/Welcome/OETest"}</grader_payload>
        </openendedparam>
    ''')

    task_xml1 = '''
                <selfassessment>
                    <hintprompt>
                        What hint about this problem would you give to someone?
                    </hintprompt>
                    <submitmessage>
                        Save Succcesful.  Thanks for participating!
                    </submitmessage>
                </selfassessment>
            '''
    task_xml2 = '''
    <openended min_score_to_attempt="1" max_score_to_attempt="1">
            <openendedparam>
                    <initial_display>Enter essay here.</initial_display>
                    <answer_display>This is the answer.</answer_display>
                    <grader_payload>{"grader_settings" : "ml_grading.conf", "problem_id" : "6.002x/Welcome/OETest"}</grader_payload>
           </openendedparam>
    </openended>'''
    definition = {'prompt': etree.XML(prompt), 'rubric': etree.XML(rubric), 'task_xml': [task_xml1, task_xml2]}
    full_definition = definition_template.format(prompt=prompt, rubric=rubric, task1=task_xml1, task2=task_xml2)
    descriptor = Mock(data=full_definition)
    test_system = test_system()
    combinedoe_container = CombinedOpenEndedModule(test_system,
                                                   location,
                                                   descriptor,
                                                   model_data={'data': full_definition, 'weight': '1'})


    def setUp(self):
        # TODO: this constructor call is definitely wrong, but neither branch
        # of the merge matches the module constructor.  Someone (Vik?) should fix this.
        self.combinedoe = CombinedOpenEndedV1Module(self.test_system,
                                                    self.location,
                                                    self.definition,
                                                    self.descriptor,
                                                    static_data=self.static_data,
                                                    metadata=self.metadata,
                                                    instance_state=self.static_data)

    def test_get_tag_name(self):
        name = self.combinedoe.get_tag_name("<t>Tag</t>")
        self.assertEqual(name, "t")

    def test_get_last_response(self):
        response_dict = self.combinedoe.get_last_response(0)
        self.assertEqual(response_dict['type'], "selfassessment")
        self.assertEqual(response_dict['max_score'], self.max_score)
        self.assertEqual(response_dict['state'], CombinedOpenEndedV1Module.INITIAL)

    def test_update_task_states(self):
        changed = self.combinedoe.update_task_states()
        self.assertFalse(changed)

        current_task = self.combinedoe.current_task
        current_task.change_state(CombinedOpenEndedV1Module.DONE)
        changed = self.combinedoe.update_task_states()

        self.assertTrue(changed)

    def test_get_max_score(self):
        changed = self.combinedoe.update_task_states()
        self.combinedoe.state = "done"
        self.combinedoe.is_scored = True
        max_score = self.combinedoe.max_score()
        self.assertEqual(max_score, 1)

    def test_container_get_max_score(self):
        #The progress view requires that this function be exposed
        max_score = self.combinedoe_container.max_score()
        self.assertEqual(max_score, None)

    def test_container_weight(self):
        weight = self.combinedoe_container.weight
        self.assertEqual(weight, 1)

    def test_container_child_weight(self):
        weight = self.combinedoe_container.child_module.weight
        self.assertEqual(weight, 1)

    def test_get_score(self):
        score_dict = self.combinedoe.get_score()
        self.assertEqual(score_dict['score'], 0)
        self.assertEqual(score_dict['total'], 1)

    def test_alternate_orderings(self):
        t1 = self.task_xml1
        t2 = self.task_xml2
        xml_to_test = [[t1], [t2], [t1, t1], [t1, t2], [t2, t2], [t2, t1], [t1, t2, t1]]
        for xml in xml_to_test:
            definition = {'prompt': etree.XML(self.prompt), 'rubric': etree.XML(self.rubric), 'task_xml': xml}
            descriptor = Mock(data=definition)
            combinedoe = CombinedOpenEndedV1Module(self.test_system,
                                                   self.location,
                                                   definition,
                                                   descriptor,
                                                   static_data=self.static_data,
                                                   metadata=self.metadata,
                                                   instance_state=self.static_data)

            changed = combinedoe.update_task_states()
            self.assertFalse(changed)

    def test_get_score_realistic(self):
        instance_state = r"""{"ready_to_reset": false, "skip_spelling_checks": true, "current_task_number": 1, "weight": 5.0, "graceperiod": "1 day 12 hours 59 minutes 59 seconds", "is_graded": "True", "task_states": ["{\"child_created\": false, \"child_attempts\": 4, \"version\": 1, \"child_history\": [{\"answer\": \"The students\\u2019 data are recorded in the table below.\\r\\n\\r\\nStarting Mass (g)\\tEnding Mass (g)\\tDifference in Mass (g)\\r\\nMarble\\t 9.8\\t 9.4\\t\\u20130.4\\r\\nLimestone\\t10.4\\t 9.1\\t\\u20131.3\\r\\nWood\\t11.2\\t11.2\\t 0.0\\r\\nPlastic\\t 7.2\\t 7.1\\t\\u20130.1\\r\\nAfter reading the group\\u2019s procedure, describe what additional information you would need in order to replicate the expe\", \"post_assessment\": \"{\\\"submission_id\\\": 3097, \\\"score\\\": 0, \\\"feedback\\\": \\\"{\\\\\\\"spelling\\\\\\\": \\\\\\\"Spelling: Ok.\\\\\\\", \\\\\\\"grammar\\\\\\\": \\\\\\\"Grammar: More grammar errors than average.\\\\\\\", \\\\\\\"markup-text\\\\\\\": \\\\\\\"the students data are recorded in the <bg>table below . starting mass</bg> g ending mass g difference in mass g marble . . . limestone . . . wood . . . plastic . . . after reading the groups <bg>procedure , describe what additional</bg> information you would need in order to replicate the <bs>expe</bs>\\\\\\\"}\\\", \\\"success\\\": true, \\\"grader_id\\\": 3233, \\\"grader_type\\\": \\\"ML\\\", \\\"rubric_scores_complete\\\": true, \\\"rubric_xml\\\": \\\"<rubric><category><description>Response Quality</description><score>0</score><option points='0'>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option><option points='1'>The response is a marginal answer to the question.  It may contain some elements of a proficient response, but it is inaccurate or incomplete.</option><option points='2'>The response is a proficient answer to the question.  It is generally correct, although it may contain minor inaccuracies.  There is limited evidence of higher-order thinking.</option><option points='3'>The response is correct, complete, and contains evidence of higher-order thinking.</option></category></rubric>\\\"}\", \"score\": 0}, {\"answer\": \"After 24 hours, remove the samples from the containers and rinse each sample with distilled water.\\r\\nAllow the samples to sit and dry for 30 minutes.\\r\\nDetermine the mass of each sample.\\r\\nThe students\\u2019 data are recorded in the table below.\\r\\n\\r\\nStarting Mass (g)\\tEnding Mass (g)\\tDifference in Mass (g)\\r\\nMarble\\t 9.8\\t 9.4\\t\\u20130.4\\r\\nLimestone\\t10.4\\t 9.1\\t\\u20131.3\\r\\nWood\\t11.2\\t11.2\\t 0.0\\r\\nPlastic\\t 7.2\\t 7.1\\t\\u20130.1\\r\\nAfter reading the\", \"post_assessment\": \"[3]\", \"score\": 3}, {\"answer\": \"To replicate the experiment, the procedure would require more detail. One piece of information that is omitted is the amount of vinegar used in the experiment. It is also important to know what temperature the experiment was kept at during the 24 hours. Finally, the procedure needs to include details about the experiment, for example if the whole sample must be submerged.\", \"post_assessment\": \"[3]\", \"score\": 3}, {\"answer\": \"e the mass of four different samples.\\r\\nPour vinegar in each of four separate, but identical, containers.\\r\\nPlace a sample of one material into one container and label. Repeat with remaining samples, placing a single sample into a single container.\\r\\nAfter 24 hours, remove the samples from the containers and rinse each sample with distilled water.\\r\\nAllow the samples to sit and dry for 30 minutes.\\r\\nDetermine the mass of each sample.\\r\\nThe students\\u2019 data are recorded in the table below.\\r\\n\", \"post_assessment\": \"[3]\", \"score\": 3}, {\"answer\": \"\", \"post_assessment\": \"[3]\", \"score\": 3}], \"max_score\": 3, \"child_state\": \"done\"}", "{\"child_created\": false, \"child_attempts\": 0, \"version\": 1, \"child_history\": [{\"answer\": \"The students\\u2019 data are recorded in the table below.\\r\\n\\r\\nStarting Mass (g)\\tEnding Mass (g)\\tDifference in Mass (g)\\r\\nMarble\\t 9.8\\t 9.4\\t\\u20130.4\\r\\nLimestone\\t10.4\\t 9.1\\t\\u20131.3\\r\\nWood\\t11.2\\t11.2\\t 0.0\\r\\nPlastic\\t 7.2\\t 7.1\\t\\u20130.1\\r\\nAfter reading the group\\u2019s procedure, describe what additional information you would need in order to replicate the expe\", \"post_assessment\": \"{\\\"submission_id\\\": 3097, \\\"score\\\": 0, \\\"feedback\\\": \\\"{\\\\\\\"spelling\\\\\\\": \\\\\\\"Spelling: Ok.\\\\\\\", \\\\\\\"grammar\\\\\\\": \\\\\\\"Grammar: More grammar errors than average.\\\\\\\", \\\\\\\"markup-text\\\\\\\": \\\\\\\"the students data are recorded in the <bg>table below . starting mass</bg> g ending mass g difference in mass g marble . . . limestone . . . wood . . . plastic . . . after reading the groups <bg>procedure , describe what additional</bg> information you would need in order to replicate the <bs>expe</bs>\\\\\\\"}\\\", \\\"success\\\": true, \\\"grader_id\\\": 3233, \\\"grader_type\\\": \\\"ML\\\", \\\"rubric_scores_complete\\\": true, \\\"rubric_xml\\\": \\\"<rubric><category><description>Response Quality</description><score>0</score><option points='0'>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option><option points='1'>The response is a marginal answer to the question.  It may contain some elements of a proficient response, but it is inaccurate or incomplete.</option><option points='2'>The response is a proficient answer to the question.  It is generally correct, although it may contain minor inaccuracies.  There is limited evidence of higher-order thinking.</option><option points='3'>The response is correct, complete, and contains evidence of higher-order thinking.</option></category></rubric>\\\"}\", \"score\": 0}, {\"answer\": \"After 24 hours, remove the samples from the containers and rinse each sample with distilled water.\\r\\nAllow the samples to sit and dry for 30 minutes.\\r\\nDetermine the mass of each sample.\\r\\nThe students\\u2019 data are recorded in the table below.\\r\\n\\r\\nStarting Mass (g)\\tEnding Mass (g)\\tDifference in Mass (g)\\r\\nMarble\\t 9.8\\t 9.4\\t\\u20130.4\\r\\nLimestone\\t10.4\\t 9.1\\t\\u20131.3\\r\\nWood\\t11.2\\t11.2\\t 0.0\\r\\nPlastic\\t 7.2\\t 7.1\\t\\u20130.1\\r\\nAfter reading the\", \"post_assessment\": \"{\\\"submission_id\\\": 3098, \\\"score\\\": 0, \\\"feedback\\\": \\\"{\\\\\\\"spelling\\\\\\\": \\\\\\\"Spelling: Ok.\\\\\\\", \\\\\\\"grammar\\\\\\\": \\\\\\\"Grammar: Ok.\\\\\\\", \\\\\\\"markup-text\\\\\\\": \\\\\\\"after hours , remove the samples from the containers and rinse each sample with distilled water . allow the samples to sit and dry for minutes . determine the mass of each sample . the students data are recorded in the <bg>table below . starting mass</bg> g ending mass g difference in mass g marble . . . limestone . . . wood . . . plastic . . . after reading the\\\\\\\"}\\\", \\\"success\\\": true, \\\"grader_id\\\": 3235, \\\"grader_type\\\": \\\"ML\\\", \\\"rubric_scores_complete\\\": true, \\\"rubric_xml\\\": \\\"<rubric><category><description>Response Quality</description><score>0</score><option points='0'>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option><option points='1'>The response is a marginal answer to the question.  It may contain some elements of a proficient response, but it is inaccurate or incomplete.</option><option points='2'>The response is a proficient answer to the question.  It is generally correct, although it may contain minor inaccuracies.  There is limited evidence of higher-order thinking.</option><option points='3'>The response is correct, complete, and contains evidence of higher-order thinking.</option></category></rubric>\\\"}\", \"score\": 0}, {\"answer\": \"To replicate the experiment, the procedure would require more detail. One piece of information that is omitted is the amount of vinegar used in the experiment. It is also important to know what temperature the experiment was kept at during the 24 hours. Finally, the procedure needs to include details about the experiment, for example if the whole sample must be submerged.\", \"post_assessment\": \"{\\\"submission_id\\\": 3099, \\\"score\\\": 3, \\\"feedback\\\": \\\"{\\\\\\\"spelling\\\\\\\": \\\\\\\"Spelling: Ok.\\\\\\\", \\\\\\\"grammar\\\\\\\": \\\\\\\"Grammar: Ok.\\\\\\\", \\\\\\\"markup-text\\\\\\\": \\\\\\\"to replicate the experiment , the procedure would require <bg>more detail . one</bg> piece of information <bg>that is omitted is the</bg> amount of vinegar used in the experiment . it is also important to know what temperature the experiment was kept at during the hours . finally , the procedure needs to include details about the experiment , for example if the whole sample must be submerged .\\\\\\\"}\\\", \\\"success\\\": true, \\\"grader_id\\\": 3237, \\\"grader_type\\\": \\\"ML\\\", \\\"rubric_scores_complete\\\": true, \\\"rubric_xml\\\": \\\"<rubric><category><description>Response Quality</description><score>3</score><option points='0'>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option><option points='1'>The response is a marginal answer to the question.  It may contain some elements of a proficient response, but it is inaccurate or incomplete.</option><option points='2'>The response is a proficient answer to the question.  It is generally correct, although it may contain minor inaccuracies.  There is limited evidence of higher-order thinking.</option><option points='3'>The response is correct, complete, and contains evidence of higher-order thinking.</option></category></rubric>\\\"}\", \"score\": 3}, {\"answer\": \"e the mass of four different samples.\\r\\nPour vinegar in each of four separate, but identical, containers.\\r\\nPlace a sample of one material into one container and label. Repeat with remaining samples, placing a single sample into a single container.\\r\\nAfter 24 hours, remove the samples from the containers and rinse each sample with distilled water.\\r\\nAllow the samples to sit and dry for 30 minutes.\\r\\nDetermine the mass of each sample.\\r\\nThe students\\u2019 data are recorded in the table below.\\r\\n\", \"post_assessment\": \"{\\\"submission_id\\\": 3100, \\\"score\\\": 0, \\\"feedback\\\": \\\"{\\\\\\\"spelling\\\\\\\": \\\\\\\"Spelling: Ok.\\\\\\\", \\\\\\\"grammar\\\\\\\": \\\\\\\"Grammar: Ok.\\\\\\\", \\\\\\\"markup-text\\\\\\\": \\\\\\\"e the mass of four different samples . pour vinegar in <bg>each of four separate</bg> , but identical , containers . place a sample of one material into one container and label . repeat with remaining samples , placing a single sample into a single container . after hours , remove the samples from the containers and rinse each sample with distilled water . allow the samples to sit and dry for minutes . determine the mass of each sample . the students data are recorded in the table below . \\\\\\\"}\\\", \\\"success\\\": true, \\\"grader_id\\\": 3239, \\\"grader_type\\\": \\\"ML\\\", \\\"rubric_scores_complete\\\": true, \\\"rubric_xml\\\": \\\"<rubric><category><description>Response Quality</description><score>0</score><option points='0'>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option><option points='1'>The response is a marginal answer to the question.  It may contain some elements of a proficient response, but it is inaccurate or incomplete.</option><option points='2'>The response is a proficient answer to the question.  It is generally correct, although it may contain minor inaccuracies.  There is limited evidence of higher-order thinking.</option><option points='3'>The response is correct, complete, and contains evidence of higher-order thinking.</option></category></rubric>\\\"}\", \"score\": 0}, {\"answer\": \"\", \"post_assessment\": \"{\\\"submission_id\\\": 3101, \\\"score\\\": 0, \\\"feedback\\\": \\\"{\\\\\\\"spelling\\\\\\\": \\\\\\\"Spelling: Ok.\\\\\\\", \\\\\\\"grammar\\\\\\\": \\\\\\\"Grammar: Ok.\\\\\\\", \\\\\\\"markup-text\\\\\\\": \\\\\\\"invalid essay .\\\\\\\"}\\\", \\\"success\\\": true, \\\"grader_id\\\": 3241, \\\"grader_type\\\": \\\"ML\\\", \\\"rubric_scores_complete\\\": true, \\\"rubric_xml\\\": \\\"<rubric><category><description>Response Quality</description><score>0</score><option points='0'>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option><option points='1'>The response is a marginal answer to the question.  It may contain some elements of a proficient response, but it is inaccurate or incomplete.</option><option points='2'>The response is a proficient answer to the question.  It is generally correct, although it may contain minor inaccuracies.  There is limited evidence of higher-order thinking.</option><option points='3'>The response is correct, complete, and contains evidence of higher-order thinking.</option></category></rubric>\\\"}\", \"score\": 0}], \"max_score\": 3, \"child_state\": \"done\"}"], "attempts": "10000", "student_attempts": 0, "due": null, "state": "done", "accept_file_upload": false, "display_name": "Science Question -- Machine Assessed"}"""
        instance_state = json.loads(instance_state)
        rubric = """
        <rubric>
            <rubric>
                <category>
                    <description>Response Quality</description>
                    <option>The response is not a satisfactory answer to the question.  It either fails to address the question or does so in a limited way, with no evidence of higher-order thinking.</option>
                    <option>The response is a marginal answer to the question.  It may contain some elements of a proficient response, but it is inaccurate or incomplete.</option>
                    <option>The response is a proficient answer to the question.  It is generally correct, although it may contain minor inaccuracies.  There is limited evidence of higher-order thinking.</option>
                    <option>The response is correct, complete, and contains evidence of higher-order thinking.</option>
                </category>
            </rubric>
        </rubric>
        """
        definition = {'prompt': etree.XML(self.prompt), 'rubric': etree.XML(rubric),
                      'task_xml': [self.task_xml1, self.task_xml2]}
        descriptor = Mock(data=definition)
        combinedoe = CombinedOpenEndedV1Module(self.test_system,
                                               self.location,
                                               definition,
                                               descriptor,
                                               static_data=self.static_data,
                                               metadata=self.metadata,
                                               instance_state=instance_state)
        score_dict = combinedoe.get_score()
        self.assertEqual(score_dict['score'], 15.0)
        self.assertEqual(score_dict['total'], 15.0)




