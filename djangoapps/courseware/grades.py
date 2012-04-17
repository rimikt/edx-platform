import courseware.content_parser as content_parser
import courseware.modules
import logging
import random
import urllib

from collections import namedtuple
from courseware import course_settings
from django.conf import settings
from lxml import etree
from models import StudentModule
from student.models import UserProfile

log = logging.getLogger("mitx.courseware")

Score = namedtuple("Score", "earned possible graded section")
SectionPercentage = namedtuple("SectionPercentage", "percentage label summary")


class CourseGrader(object):
    """
    A course grader takes the totaled scores for each graded section (that a student has 
    started) in the course. From these scores, the grader calculates an overall percentage 
    grade. The grader should also generate information about how that score was calculated,
    to be displayed in graphs or charts.
    
    A grader has one required method, grade(), which is passed a grade_sheet. The grade_sheet
    contains scores for all graded section that the student has started. If a student has
    a score of 0 for that section, it may be missing from the grade_sheet. The grade_sheet
    is keyed by section format. Each value is a list of Score namedtuples for each section
    that has the matching section format.
    
    The grader outputs a dictionary with the following keys:
    - percent: Contaisn a float value, which is the final percentage score for the student.
    - section_breakdown: This is a list of dictionaries which provide details on sections
    that were graded. These are used for display in a graph or chart. The format for a 
    section_breakdown dictionary is explained below.
    - grade_breakdown: This is a list of dictionaries which provide details on the contributions
    of the final percentage grade. This is a higher level breakdown, for when the grade is constructed
    of a few very large sections (such as Homeworks, Labs, a Midterm, and a Final). The format for
    a grade_breakdown is explained below. This section is optional.
    
    A dictionary in the section_breakdown list has the following keys:
    percent: A float percentage for the section.
    label: A short string identifying the section. Preferably fixed-length. E.g. "HW  3".
    detail: A string explanation of the score. E.g. "Homework 1 - Ohms Law - 83% (5/6)"
    category: A string identifying the category. Items with the same category are grouped together
    in the display (for example, by color).
    prominent: A boolean value indicating that this section should be displayed as more prominent
    than other items.
    
    A dictionary in the grade_breakdown list has the following keys:
    percent: A float percentage in the breakdown. All percents should add up to the final percentage.
    detail: A string explanation of this breakdown. E.g. "Homework - 10% of a possible 15%"
    category: A string identifying the category. Items with the same category are grouped together
    in the display (for example, by color).
    
    
    """
    def grade(self, grade_sheet):
        raise NotImplementedError
    
    
    @classmethod
    def graderFromConf(cls, conf):
        if isinstance(conf, CourseGrader):
            return conf
        
        subgraders = []
        for subgraderconf in conf:
            subgraderconf = subgraderconf.copy()
            weight = subgraderconf.pop("weight", 0)
            try:
                if 'min_count' in subgraderconf:
                    #This is an AssignmentFormatGrader
                    subgrader = AssignmentFormatGrader(**subgraderconf)
                    subgraders.append( (subgrader, subgrader.category, weight) ) 
                elif 'section_name' in subgraderconf:
                    #This is an SingleSectionGrader
                    subgrader = SingleSectionGrader(**subgraderconf)
                    subgraders.append( (subgrader, subgrader.category, weight) )
                else:
                    raise ValueError("Configuration has no appropriate grader class.")
                    
            except TypeError as error:
                 log.error("Unable to parse grader configuration:\n" + subgraderconf + "\nError was:\n" + error)
            except ValueError as error:
                 log.error("Unable to parse grader configuration:\n" + subgraderconf + "\nError was:\n" + error)
        
        return WeightedSubsectionsGrader( subgraders )
        
    
class WeightedSubsectionsGrader(CourseGrader):
    """
    This grader takes a list of tuples containing (grader, category_name, weight) and computes
    a final grade by totalling the contribution of each sub grader and multiplying it by the
    given weight. For example, the sections may be 
    [ (homeworkGrader, "Homework", 0.15), (labGrader, "Labs", 0.15), (midtermGrader, "Midterm", 0.30), (finalGrader, "Final", 0.40) ]
    All items in section_breakdown for each subgrader will be combined. A grade_breakdown will be
    composed using the score from each grader.
    
    Note that the sum of the weights is not take into consideration. If the weights add up to
    a value > 1, the student may end up with a percent > 100%. This allows for sections that
    are extra credit.
    """
    def __init__(self, sections):
        self.sections = sections
        
    def grade(self, grade_sheet):
        total_percent = 0.0
        section_breakdown = []
        grade_breakdown = []
        
        for subgrader, section_name, weight in self.sections:
            subgrade_result = subgrader.grade(grade_sheet)
            
            weightedPercent = subgrade_result['percent'] * weight
            section_detail = "{0} = {1:.1%} of a possible {2:.0%}".format(section_name, weightedPercent, weight)
            
            total_percent += weightedPercent
            section_breakdown += subgrade_result['section_breakdown']
            grade_breakdown.append( {'percent' : weightedPercent, 'detail' : section_detail, 'category' : section_name} )
            
        return {'percent' : total_percent,
                'section_breakdown' : section_breakdown,
                'grade_breakdown' : grade_breakdown}


class SingleSectionGrader(CourseGrader):
    """
    This grades a single section with the format section_format and the name section_name.
    
    If the section_name is not appropriate for the short short_label or category, they each may
    be specified individually.
    """
    def __init__(self, section_format, section_name, short_label = None, category = None):
        self.section_format = section_format
        self.section_name = section_name
        self.short_label = short_label or section_name
        self.category = category or section_name
    
    def grade(self, grade_sheet):
        foundScore = None
        if self.section_format in grade_sheet:
            for score in grade_sheet[self.section_format]:
                if score.section == self.section_name:
                    foundScore = score
                    break
        
        if foundScore:
            percent = foundScore.earned / float(foundScore.possible) 
            detail = "{name} - {percent:.0%} ({earned:.3n}/{possible:.3n})".format( name = self.section_name, 
                                                                        percent = percent,
                                                                        earned = float(foundScore.earned),
                                                                        possible = float(foundScore.possible))
            
        else:
            percent = 0.0
            detail = "{name} - 0% (?/?)".format(name = self.section_name)
            
            if settings.GENERATE_PROFILE_SCORES:
                points_possible = random.randrange(50, 100)
                points_earned = random.randrange(40, points_possible)
                percent = points_earned / float(points_possible)
                detail = "{name} - {percent:.0%} ({earned:.3n}/{possible:.3n})".format( name = self.section_name, 
                                                                        percent = percent,
                                                                        earned = float(points_earned),
                                                                        possible = float(points_possible))

            
            
        
        breakdown = [{'percent': percent, 'label': self.short_label, 'detail': detail, 'category': self.category, 'prominent': True}]
            
        return {'percent' : percent,
                'section_breakdown' : breakdown,
                #No grade_breakdown here
                }
     
class AssignmentFormatGrader(CourseGrader):
    """
    Grades all sections specified in course_format with an equal weight. A specified
    number of lowest scores can be dropped from the calculation. The minimum number of
    sections in this format must be specified (even if those sections haven't been
    written yet).
    
    min_count defines how many assignments are expected throughout the course. Placeholder
    scores (of 0) will be inserted if the number of matching sections in the course is < min_count.
    If there number of matching sections in the course is > min_count, min_count will be ignored.
    
    category should be presentable to the user, but may not appear. When the grade breakdown is 
    displayed, scores from the same category will be similar (for example, by color).
    
    section_type is a string that is the type of a singular section. For example, for Labs it
    would be "Lab". This defaults to be the same as category.
    
    short_label is similar to section_type, but shorter. For example, for Homework it would be
    "HW".
    
    """
    def __init__(self, course_format, min_count, drop_count, category = None, section_type = None, short_label = None):
        self.course_format = course_format
        self.min_count = min_count
        self.drop_count = drop_count
        self.category = category or self.course_format
        self.section_type = section_type or self.course_format
        self.short_label = short_label or self.course_format
    
    def grade(self, grade_sheet):
        def totalWithDrops(breakdown, drop_count):
            #create an array of tuples with (index, mark), sorted by mark['percent'] descending
            sorted_breakdown = sorted( enumerate(breakdown), key=lambda x: -x[1]['percent'] )
            # A list of the indices of the dropped scores
            dropped_indices = []
            if drop_count > 0:
                dropped_indices = [x[0] for x in sorted_breakdown[-drop_count:]]
            aggregate_score = 0
            for index, mark in enumerate(breakdown):
                if index not in dropped_indices:
                    aggregate_score += mark['percent']
            
            if (len(breakdown) - drop_count > 0):
                aggregate_score /= len(breakdown) - drop_count
        
            return aggregate_score, dropped_indices
        
        #Figure the homework scores
        scores = grade_sheet.get(self.course_format, [])
        breakdown = []
        for i in range( max(self.min_count, len(scores)) ):
            if i < len(scores):
                percentage = scores[i].earned / float(scores[i].possible)
                summary = "{section_type} {index} - {name} - {percent:.0%} ({earned:.3n}/{possible:.3n})".format(index = i+1, 
                                                                section_type = self.section_type,
                                                                name = scores[i].section,
                                                                percent = percentage, 
                                                                earned = float(scores[i].earned), 
                                                                possible = float(scores[i].possible) )
            else:
                percentage = 0
                summary = "{section_type} {index} Unreleased - 0% (?/?)".format(index = i+1, section_type = self.section_type)
        
                if settings.GENERATE_PROFILE_SCORES:
                    points_possible = random.randrange(10, 50)
                    points_earned = random.randrange(5, points_possible)
                    percentage = points_earned / float(points_possible)
                    summary = "{section_type} {index} - {name} - {percent:.0%} ({earned:.3n}/{possible:.3n})".format(index = i+1, 
                                                                    section_type = self.section_type,
                                                                    name = "Randomly Generated",
                                                                    percent = percentage, 
                                                                    earned = float(points_earned), 
                                                                    possible = float(points_possible) )
        
            short_label = "{short_label} {index:02d}".format(index = i+1, short_label = self.short_label)
            
            breakdown.append( {'percent': percentage, 'label': short_label, 'detail': summary, 'category': self.category} )
        
        total_percent, dropped_indices = totalWithDrops(breakdown, self.drop_count)
        
        for dropped_index in dropped_indices:
            breakdown[dropped_index]['mark'] = {'detail': "The lowest {drop_count} {section_type} scores are dropped.".format(drop_count = self.drop_count, section_type=self.section_type) }
        
        
        total_detail = "{section_type} Average = {percent:.0%}".format(percent = total_percent, section_type = self.section_type)
        total_label = "{short_label} Avg".format(short_label = self.short_label)
        breakdown.append( {'percent': total_percent, 'label': total_label, 'detail': total_detail, 'category': self.category, 'prominent': True} )
        
        
        return {'percent' : total_percent,
                'section_breakdown' : breakdown,
                #No grade_breakdown here
                }

def get_score(user, problem, cache):
    ## HACK: assumes max score is fixed per problem
    id = problem.get('id')
    correct = 0.0
    
    # If the ID is not in the cache, add the item
    if id not in cache:
        module = StudentModule(module_type = 'problem',  # TODO: Move into StudentModule.__init__?
                               module_id = id,
                               student = user, 
                               state = None, 
                               grade = 0,
                               max_grade = None,
                               done = 'i')
        cache[id] = module

    # Grab the # correct from cache
    if id in cache:
        response = cache[id]
        if response.grade!=None:
            correct=float(response.grade)
        
    # Grab max grade from cache, or if it doesn't exist, compute and save to DB
    if id in cache and response.max_grade != None:
        total = response.max_grade
    else:
        total=float(courseware.modules.capa_module.Module(etree.tostring(problem), "id").max_score())
        response.max_grade = total
        response.save()
        
    #Now we re-weight the problem, if specified
    weight = problem.get("weight", None)
    if weight:
        weight = float(weight) 
        correct = correct * weight / total
        total = weight        

    return (correct, total)

def grade_sheet(student):
    """
    This pulls a summary of all problems in the course. It returns a dictionary with two datastructures:
    
    - courseware_summary is a summary of all sections with problems in the course. It is organized as an array of chapters,
    each containing an array of sections, each containing an array of scores. This contains information for graded and ungraded
    problems, and is good for displaying a course summary with due dates, etc.
    
    - grade_summary is the output from the course grader. More information on the format is in the docstring for CourseGrader.
    """
    dom=content_parser.course_file(student)
    course = dom.xpath('//course/@name')[0]
    xmlChapters = dom.xpath('//course[@name=$course]/chapter', course=course)

    responses=StudentModule.objects.filter(student=student)
    response_by_id = {}
    for response in responses:
        response_by_id[response.module_id] = response
    
    
    totaled_scores = {}
    chapters=[]
    for c in xmlChapters:
        sections = []
        chname=c.get('name')
        
        
        for s in dom.xpath('//course[@name=$course]/chapter[@name=$chname]/section', 
                           course=course, chname=chname):
            problems=dom.xpath('//course[@name=$course]/chapter[@name=$chname]/section[@name=$section]//problem', 
                           course=course, chname=chname, section=s.get('name'))

            graded = True if s.get('graded') == "true" else False
            scores=[]
            if len(problems)>0:
                for p in problems:
                    (correct,total) = get_score(student, p, response_by_id)
                    
                    if settings.GENERATE_PROFILE_SCORES:
                        if total > 1:
                            correct = random.randrange( max(total-2, 1) , total + 1 )
                        else:
                            correct = total
                    scores.append( Score(correct,total, graded, p.get("name")) )

                section_total, graded_total = aggregate_scores(scores, s.get("name"))
                #Add the graded total to totaled_scores
                format = s.get('format', "")
                subtitle = s.get('subtitle', format)
                if format and graded_total[1] > 0:
                    format_scores = totaled_scores.get(format, [])
                    format_scores.append( graded_total )
                    totaled_scores[ format ] = format_scores

                section_score={'section':s.get("name"),
                       'scores':scores,
                       'section_total' : section_total,
                       'format' : format,
                       'subtitle' : subtitle,
                       'due' : s.get("due") or "",
                       'graded' : graded,
                       }
                sections.append(section_score)

        chapters.append({'course':course,
                         'chapter' : c.get("name"),
                         'sections' : sections,})
    
        
    grader = CourseGrader.graderFromConf(course_settings.GRADER)
    #TODO: We should cache this grader object
    grade_summary = grader.grade(totaled_scores)
    
    return {'courseware_summary' : chapters,
            'grade_summary' : grade_summary}

def aggregate_scores(scores, section_name = "summary"):    
    total_correct_graded = sum(score.earned for score in scores if score.graded)
    total_possible_graded = sum(score.possible for score in scores if score.graded)
    
    total_correct = sum(score.earned for score in scores)
    total_possible = sum(score.possible for score in scores)
        
    #regardless of whether or not it is graded
    all_total = Score(total_correct, 
                          total_possible,
                          False,
                          section_name)
    #selecting only graded things
    graded_total = Score(total_correct_graded, 
                         total_possible_graded, 
                         True, 
                         section_name)

    return all_total, graded_total
