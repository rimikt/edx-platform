import unittest

import draganddrop
from draganddrop import PositionsCompare


class Test_PositionsCompare(unittest.TestCase):
    """ describe"""

    def test_nested_list_and_list1(self):
        self.assertEqual(PositionsCompare([[1, 2], 40]), PositionsCompare([1, 3]))

    def test_nested_list_and_list2(self):
        self.assertNotEqual(PositionsCompare([1, 12]), PositionsCompare([1, 1]))

    def test_list_and_list1(self):
        self.assertNotEqual(PositionsCompare([[1, 2], 12]), PositionsCompare([1, 15]))

    def test_list_and_list2(self):
        self.assertEqual(PositionsCompare([1, 11]), PositionsCompare([1, 1]))

    def test_numerical_list_and_string_list(self):
        self.assertNotEqual(PositionsCompare([1, 2]), PositionsCompare(["1"]))

    def test_string_and_string_list1(self):
        self.assertEqual(PositionsCompare("1"), PositionsCompare(["1"]))

    def test_string_and_string_list2(self):
        self.assertEqual(PositionsCompare("abc"), PositionsCompare("abc"))

    def test_string_and_string_list3(self):
        self.assertNotEqual(PositionsCompare("abd"), PositionsCompare("abe"))

    def test_float_and_string(self):
        self.assertNotEqual(PositionsCompare([3.5, 5.7]), PositionsCompare(["1"]))

    def test_floats_and_ints(self):
        self.assertEqual(PositionsCompare([3.5, 4.5]), PositionsCompare([5, 7]))


class Test_DragAndDrop_Grade(unittest.TestCase):

    def test_targets_true(self):
        user_input = '{"draggables": [{"1": "t1"}, \
         {"name_with_icon": "t2"}]}'
        correct_answer = {'1':              't1', 'name_with_icon': 't2'}
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_targets_false(self):
        user_input = '{"draggables": [{"1": "t1"}, \
        {"name_with_icon": "t2"}]}'
        correct_answer = {'1':              't3', 'name_with_icon': 't2'}
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_multiple_images_per_target_true(self):
        user_input = '{\
        "draggables": [{"1": "t1"}, {"name_with_icon": "t2"}, \
        {"2": "t1"}]}'
        correct_answer = {'1':              't1', 'name_with_icon': 't2',
        '2': 't1'}
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_multiple_images_per_target_false(self):
        user_input = '{\
        "draggables": [{"1": "t1"}, {"name_with_icon": "t2"}, \
        {"2": "t1"}]}'
        correct_answer = {'1':              't2', 'name_with_icon': 't2',
        '2': 't1'}
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_targets_and_positions(self):
        user_input = '{"draggables": [{"1": [10,10]}, \
         {"name_with_icon": [[10,10],4]}]}'
        correct_answer = {'1':  [10, 10], 'name_with_icon': [[10, 10], 4]}
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_position_and_targets(self):
        user_input = '{"draggables": [{"1": "t1"}, {"name_with_icon": "t2"}]}'
        correct_answer = {'1':    't1', 'name_with_icon': 't2'}
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_positions_exact(self):
        user_input = '{"draggables": \
        [{"1": [10, 10]}, {"name_with_icon": [20, 20]}]}'
        correct_answer = {'1':   [10, 10], 'name_with_icon': [20, 20]}
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_positions_false(self):
        user_input = '{"draggables": \
        [{"1": [10, 10]}, {"name_with_icon": [20, 20]}]}'
        correct_answer = {'1':   [25, 25], 'name_with_icon': [20, 20]}
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_positions_true_in_radius(self):
        user_input = '{"draggables": \
        [{"1": [10, 10]}, {"name_with_icon": [20, 20]}]}'
        correct_answer = {'1':   [14, 14], 'name_with_icon': [20, 20]}
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_positions_true_in_manual_radius(self):
        user_input = '{"draggables": \
        [{"1": [10, 10]}, {"name_with_icon": [20, 20]}]}'
        correct_answer = {'1':   [[40, 10], 30], 'name_with_icon': [20, 20]}
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_positions_false_in_manual_radius(self):
        user_input = '{"draggables": \
        [{"1": [10, 10]}, {"name_with_icon": [20, 20]}]}'
        correct_answer = {'1': [[40, 10], 29], 'name_with_icon': [20, 20]}
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_correct_answer_not_has_key_from_user_answer(self):
        user_input = '{"draggables": [{"1": "t1"}, \
        {"name_with_icon": "t2"}]}'
        correct_answer = {'3':   't3', 'name_with_icon': 't2'}
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_anywhere(self):
        """Draggables can be places anywhere on base image.
            Place grass in the middle of the image and ant in the
            right upper corner."""
        user_input = '{"draggables": \
        [{"ant":[610.5,57.449951171875]},{"grass":[322.5,199.449951171875]}]}'

        correct_answer = {'grass':     [[300, 200], 200], 'ant': [[500, 0], 200]}
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_lcao_correct(self):
        """Describe carbon molecule in LCAO-MO"""
        user_input = '{"draggables":[{"1":"s_left"}, \
        {"5":"s_right"},{"4":"s_sigma"},{"6":"s_sigma_star"},{"7":"p_left_1"}, \
        {"8":"p_left_2"},{"10":"p_right_1"},{"9":"p_right_2"}, \
        {"2":"p_pi_1"},{"3":"p_pi_2"},{"11":"s_sigma_name"}, \
        {"13":"s_sigma_star_name"},{"15":"p_pi_name"},{"16":"p_pi_star_name"}, \
        {"12":"p_sigma_name"},{"14":"p_sigma_star_name"}]}'

        correct_answer = [{
        'draggables': ['1', '2', '3', '4', '5', '6'],
        'targets': [
            's_left', 's_right', 's_sigma', 's_sigma_star', 'p_pi_1', 'p_pi_2'
        ],
            'rule': 'anyof'
        }, {
            'draggables': ['7', '8', '9', '10'],
            'targets': ['p_left_1', 'p_left_2', 'p_right_1', 'p_right_2'],
            'rule': 'anyof'
        }, {
            'draggables': ['11', '12'],
            'targets': ['s_sigma_name', 'p_sigma_name'],
            'rule': 'anyof'
        }, {
            'draggables': ['13', '14'],
            'targets': ['s_sigma_star_name', 'p_sigma_star_name'],
            'rule': 'anyof'
        }, {
            'draggables': ['15'],
            'targets': ['p_pi_name'],
            'rule': 'anyof'
        }, {
            'draggables': ['16'],
            'targets': ['p_pi_star_name'],
            'rule': 'anyof'
        }]

        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_lcao_extra_element_incorrect(self):
        """Describe carbon molecule in LCAO-MO"""
        user_input = '{"draggables":[{"1":"s_left"}, \
        {"5":"s_right"},{"4":"s_sigma"},{"6":"s_sigma_star"},{"7":"p_left_1"}, \
        {"8":"p_left_2"},{"17":"p_left_3"},{"10":"p_right_1"},{"9":"p_right_2"}, \
        {"2":"p_pi_1"},{"3":"p_pi_2"},{"11":"s_sigma_name"}, \
        {"13":"s_sigma_star_name"},{"15":"p_pi_name"},{"16":"p_pi_star_name"}, \
        {"12":"p_sigma_name"},{"14":"p_sigma_star_name"}]}'

        correct_answer = [{
        'draggables': ['1', '2', '3', '4', '5', '6'],
        'targets': [
            's_left', 's_right', 's_sigma', 's_sigma_star', 'p_pi_1', 'p_pi_2'
            ],
            'rule': 'anyof'
        }, {
            'draggables': ['7', '8', '9', '10'],
            'targets': ['p_left_1', 'p_left_2', 'p_right_1', 'p_right_2'],
            'rule': 'anyof'
        }, {
            'draggables': ['11', '12'],
            'targets': ['s_sigma_name', 'p_sigma_name'],
            'rule': 'anyof'
        }, {
            'draggables': ['13', '14'],
            'targets': ['s_sigma_star_name', 'p_sigma_star_name'],
            'rule': 'anyof'
        }, {
            'draggables': ['15'],
            'targets': ['p_pi_name'],
            'rule': 'anyof'
        }, {
            'draggables': ['16'],
            'targets': ['p_pi_star_name'],
            'rule': 'anyof'
        }]

        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_reuse_draggable_no_mupliples(self):
        """Test reusable draggables (no mupltiple draggables per target)"""
        user_input = '{"draggables":[{"1":"target1"}, \
        {"2":"target2"},{"1":"target3"},{"2":"target4"},{"2":"target5"}, \
        {"3":"target6"}]}'
        correct_answer = [
        {
            'draggables': ['1'],
            'targets': ['target1',  'target3'],
            'rule': 'anyof'
        },
        {
            'draggables': ['2'],
            'targets': ['target2', 'target4', 'target5'],
            'rule': 'anyof'
        },
        {
            'draggables': ['3'],
            'targets': ['target6'],
            'rule': 'anyof'
        }]
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_reuse_draggable_with_mupliples(self):
        """Test reusable draggables with mupltiple draggables per target"""
        user_input = '{"draggables":[{"1":"target1"}, \
        {"2":"target2"},{"1":"target1"},{"2":"target4"},{"2":"target4"}, \
        {"3":"target6"}]}'
        correct_answer = [
        {
            'draggables': ['1'],
            'targets': ['target1',  'target3'],
            'rule': 'anyof'
        },
        {
            'draggables': ['2'],
            'targets': ['target2', 'target4'],
            'rule': 'anyof'
        },
        {
            'draggables': ['3'],
            'targets': ['target6'],
            'rule': 'anyof'
        }]
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_reuse_many_draggable_with_mupliples(self):
        """Test reusable draggables with mupltiple draggables per target"""
        user_input = '{"draggables":[{"1":"target1"}, \
        {"2":"target2"},{"1":"target1"},{"2":"target4"},{"2":"target4"}, \
        {"3":"target6"}, {"4": "target3"}, {"5": "target4"}, \
        {"5": "target5"}, {"6": "target2"}]}'
        correct_answer = [
        {
            'draggables': ['1', '4'],
            'targets': ['target1',  'target3'],
            'rule': 'anyof'
        },
        {
            'draggables': ['2', '6'],
            'targets': ['target2', 'target4'],
            'rule': 'anyof'
        },
        {
            'draggables': ['5'],
            'targets': ['target4', 'target5'],
            'rule': 'anyof'
        },
        {
            'draggables': ['3'],
            'targets': ['target6'],
            'rule': 'anyof'
        }]
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_reuse_many_draggable_with_mupliples_wrong(self):
        """Test reusable draggables with mupltiple draggables per target"""
        user_input = '{"draggables":[{"1":"target1"}, \
        {"2":"target2"},{"1":"target1"}, \
        {"2":"target3"}, \
        {"2":"target4"}, \
        {"3":"target6"}, {"4": "target3"}, {"5": "target4"}, \
        {"5": "target5"}, {"6": "target2"}]}'
        correct_answer = [
        {
            'draggables': ['1', '4'],
            'targets': ['target1',  'target3'],
            'rule': 'anyof'
        },
        {
            'draggables': ['2', '6'],
            'targets': ['target2', 'target4'],
            'rule': 'anyof'
        },
        {
            'draggables': ['5'],
            'targets': ['target4', 'target5'],
            'rule': 'anyof'
        },
        {
            'draggables': ['3'],
            'targets': ['target6'],
            'rule': 'anyof'
        }]
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_label_10_targets_with_a_b_c_false(self):
        """Test reusable draggables (no mupltiple draggables per target)"""
        user_input = '{"draggables":[{"a":"target1"}, \
        {"b":"target2"},{"c":"target3"},{"a":"target4"},{"b":"target5"}, \
        {"c":"target6"}, {"a":"target7"},{"b":"target8"},{"c":"target9"}, \
         {"a":"target1"}]}'
        correct_answer = [
        {
            'draggables': ['a'],
            'targets': ['target1',  'target4', 'target7', 'target10'],
            'rule': 'unordered_equal'
        },
        {
            'draggables': ['b'],
            'targets': ['target2', 'target5', 'target8'],
            'rule': 'unordered_equal'
        },
        {
            'draggables': ['c'],
            'targets': ['target3', 'target6', 'target9'],
            'rule': 'unordered_equal'
        }]
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_label_10_targets_with_a_b_c_(self):
        """Test reusable draggables (no mupltiple draggables per target)"""
        user_input = '{"draggables":[{"a":"target1"}, \
        {"b":"target2"},{"c":"target3"},{"a":"target4"},{"b":"target5"}, \
        {"c":"target6"}, {"a":"target7"},{"b":"target8"},{"c":"target9"}, \
         {"a":"target10"}]}'
        correct_answer = [
        {
            'draggables': ['a'],
            'targets': ['target1',  'target4', 'target7', 'target10'],
            'rule': 'unordered_equal'
        },
        {
            'draggables': ['b'],
            'targets': ['target2', 'target5', 'target8'],
            'rule': 'unordered_equal'
        },
        {
            'draggables': ['c'],
            'targets': ['target3', 'target6', 'target9'],
            'rule': 'unordered_equal'
        }]
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_label_10_targets_with_a_b_c_multiple(self):
        """Test reusable draggables  (mupltiple draggables per target)"""
        user_input = '{"draggables":[{"a":"target1"}, \
        {"b":"target2"},{"c":"target3"},{"b":"target5"}, \
        {"c":"target6"}, {"a":"target7"},{"b":"target8"},{"c":"target9"}, \
         {"a":"target1"}]}'
        correct_answer = [
        {
            'draggables': ['a', 'a', 'a'],
            'targets': ['target1',  'target4', 'target7', 'target10'],
            'rule': 'anyof+number'
        },
        {
            'draggables': ['b', 'b', 'b'],
            'targets': ['target2', 'target5', 'target8'],
            'rule': 'anyof+number'
        },
        {
            'draggables': ['c', 'c', 'c'],
            'targets': ['target3', 'target6', 'target9'],
            'rule': 'anyof+number'
        }]
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_label_10_targets_with_a_b_c_multiple_false(self):
        """Test reusable draggables  (mupltiple draggables per target)"""
        user_input = '{"draggables":[{"a":"target1"}, \
        {"b":"target2"},{"c":"target3"},{"a":"target4"},{"b":"target5"}, \
        {"c":"target6"}, {"a":"target7"},{"b":"target8"},{"c":"target9"}, \
         {"a":"target1"}]}'
        correct_answer = [
        {
            'draggables': ['a', 'a', 'a'],
            'targets': ['target1',  'target4', 'target7', 'target10'],
            'rule': 'anyof+number'
        },
        {
            'draggables': ['b', 'b', 'b'],
            'targets': ['target2', 'target5', 'target8'],
            'rule': 'anyof+number'
        },
        {
            'draggables': ['c', 'c', 'c'],
            'targets': ['target3', 'target6', 'target9'],
            'rule': 'anyof+number'
        }]
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_label_10_targets_with_a_b_c_reused(self):
        """Test a b c in 10 labels reused"""
        user_input = '{"draggables":[{"a":"target1"}, \
        {"b":"target2"},{"c":"target3"},{"b":"target5"}, \
        {"c":"target6"}, {"b":"target8"},{"c":"target9"}, \
         {"a":"target10"}]}'
        correct_answer = [
        {
            'draggables': ['a', 'a'],
            'targets': ['target1',   'target10'],
            'rule': 'unordered_equal+number'
        },
        {
            'draggables': ['b', 'b', 'b'],
            'targets': ['target2', 'target5', 'target8'],
            'rule': 'unordered_equal+number'
        },
        {
            'draggables': ['c', 'c', 'c'],
            'targets': ['target3', 'target6', 'target9'],
            'rule': 'unordered_equal+number'
        }]
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_label_10_targets_with_a_b_c_reused_false(self):
        """Test a b c in 10 labels reused false"""
        user_input = '{"draggables":[{"a":"target1"}, \
        {"b":"target2"},{"c":"target3"},{"b":"target5"}, {"a":"target8"},\
        {"c":"target6"}, {"b":"target8"},{"c":"target9"}, \
         {"a":"target10"}]}'
        correct_answer = [
        {
            'draggables': ['a', 'a'],
            'targets': ['target1',   'target10'],
            'rule': 'unordered_equal+number'
        },
        {
            'draggables': ['b', 'b', 'b'],
            'targets': ['target2', 'target5', 'target8'],
            'rule': 'unordered_equal+number'
        },
        {
            'draggables': ['c', 'c', 'c'],
            'targets': ['target3', 'target6', 'target9'],
            'rule': 'unordered_equal+number'
        }]
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_mixed_reuse_and_not_reuse(self):
        """Test reusable draggables """
        user_input = '{"draggables":[{"a":"target1"}, \
        {"b":"target2"},{"c":"target3"}, {"a":"target4"},\
         {"a":"target5"}]}'
        correct_answer = [
        {
            'draggables': ['a', 'b'],
            'targets': ['target1',   'target2', 'target4', 'target5'],
            'rule': 'anyof'
        },
        {
            'draggables': ['c'],
            'targets': ['target3'],
            'rule': 'exact'
        }]
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_mixed_reuse_and_not_reuse_number(self):
        """Test reusable draggables with number """
        user_input = '{"draggables":[{"a":"target1"}, \
        {"b":"target2"},{"c":"target3"}, {"a":"target4"}]}'
        correct_answer = [
        {
            'draggables': ['a', 'a', 'b'],
            'targets': ['target1',   'target2', 'target4'],
            'rule': 'anyof+number'
        },
        {
            'draggables': ['c'],
            'targets': ['target3'],
            'rule': 'exact'
        }]
        self.assertTrue(draganddrop.grade(user_input, correct_answer))

    def test_mixed_reuse_and_not_reuse_number_false(self):
        """Test reusable draggables with numbers, but wrong"""
        user_input = '{"draggables":[{"a":"target1"}, \
        {"b":"target2"},{"c":"target3"}, {"a":"target4"}, {"a":"target10"}]}'
        correct_answer = [
        {
            'draggables': ['a', 'a', 'b'],
            'targets': ['target1',   'target2', 'target4', 'target10'],
            'rule': 'anyof_number'
        },
        {
            'draggables': ['c'],
            'targets': ['target3'],
            'rule': 'exact'
        }]
        self.assertFalse(draganddrop.grade(user_input, correct_answer))

    def test_alternative_correct_answer(self):
        user_input = '{"draggables":[{"name_with_icon":"t1"},\
        {"name_with_icon":"t1"},{"name_with_icon":"t1"},{"name4":"t1"}, \
        {"name4":"t1"}]}'
        correct_answer = [
        {'draggables': ['name4'], 'targets': ['t1', 't1'], 'rule': 'exact'},
        {'draggables': ['name_with_icon'], 'targets': ['t1', 't1', 't1'],
        'rule': 'exact'}
        ]
        self.assertTrue(draganddrop.grade(user_input, correct_answer))


class Test_DragAndDrop_Populate(unittest.TestCase):

    def test_1(self):
        dnd = draganddrop.DragAndDrop()
        correct_answer = {'1': [[40, 10], 29], 'name_with_icon': [20, 20]}
        user_input = '{"draggables": \
        [{"1": [10, 10]}, {"name_with_icon": [20, 20]}]}'
        dnd.populate(correct_answer, user_input)

        correct_groups = {'1': ['name_with_icon'], '0': ['1']}
        correct_positions = {'1': {'exact': [[20, 20]]}, '0': {'exact': [[[40, 10], 29]]}}
        user_groups = {'1': [u'name_with_icon'], '0': [u'1']}
        user_positions = {'1': {'user': [[20, 20]]}, '0': {'user': [[10, 10]]}}

        self.assertEqual(correct_groups, dnd.correct_groups)
        self.assertEqual(correct_positions, dnd.correct_positions)
        self.assertEqual(user_groups, dnd.user_groups)
        self.assertEqual(user_positions, dnd.user_positions)


class Test_DraAndDrop_Compare_Positions(unittest.TestCase):

    def test_1(self):
        dnd = draganddrop.DragAndDrop()
        self.assertTrue(dnd.compare_positions(correct=[[1, 1], [2, 3]],
                                              user=[[2, 3], [1, 1]],
                                              flag='anyof'))

    def test_2a(self):
        dnd = draganddrop.DragAndDrop()
        self.assertTrue(dnd.compare_positions(correct=[[1, 1], [2, 3]],
                                               user=[[2, 3], [1, 1]],
                                               flag='exact'))

    def test_2b(self):
        dnd = draganddrop.DragAndDrop()
        self.assertFalse(dnd.compare_positions(correct=[[1, 1], [2, 3]],
                                               user=[[2, 13], [1, 1]],
                                               flag='exact'))

    def test_3(self):
        dnd = draganddrop.DragAndDrop()
        self.assertFalse(dnd.compare_positions(correct=["a", "b"],
                                               user=["a", "b", "c"],
                                               flag='anyof'))

    def test_4(self):
        dnd = draganddrop.DragAndDrop()
        self.assertTrue(dnd.compare_positions(correct=["a", "b", "c"],
                                              user=["a", "b"],
                                              flag='anyof'))

    def test_5(self):
        dnd = draganddrop.DragAndDrop()
        self.assertFalse(dnd.compare_positions(correct=["a", "b", "c"],
                                               user=["a", "c", "b"],
                                               flag='exact'))

    def test_6(self):
        dnd = draganddrop.DragAndDrop()
        self.assertTrue(dnd.compare_positions(correct=["a", "b", "c"],
                                               user=["a", "c", "b"],
                                               flag='anyof'))

    def test_7(self):
        dnd = draganddrop.DragAndDrop()
        self.assertFalse(dnd.compare_positions(correct=["a", "b", "b"],
                                               user=["a", "c", "b"],
                                               flag='anyof'))


def suite():

    testcases = [Test_PositionsCompare,
                   Test_DragAndDrop_Populate,
                   Test_DragAndDrop_Grade,
                   Test_DraAndDrop_Compare_Positions
                 ]
    suites = []
    for testcase in testcases:
        suites.append(unittest.TestLoader().loadTestsFromTestCase(testcase))
    return unittest.TestSuite(suites)

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(suite())
