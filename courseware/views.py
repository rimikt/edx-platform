import json
import logging
import os
import sys
import StringIO
import urllib
import uuid

from django.conf import settings
from django.core.context_processors import csrf
from django.contrib.auth.models import User
from django.http import HttpResponse, Http404
from django.shortcuts import redirect
from django.template import Context, loader
from mitxmako.shortcuts import render_to_response, render_to_string
from django.db import connection

from lxml import etree

from module_render import render_module, modx_dispatch
from models import StudentModule
from student.models import UserProfile

import courseware.content_parser as content_parser
import courseware.modules.capa_module

log = logging.getLogger("mitx.courseware")

etree.set_default_parser(etree.XMLParser(dtd_validation=False, load_dtd=False,
                                         remove_comments = True))

template_imports={'urllib':urllib}

def profile(request):
    ''' User profile. Show username, location, etc, as well as grades .
        We need to allow the user to change some of these settings .'''
    if not request.user.is_authenticated():
        return redirect('/')
    
    dom=content_parser.course_file(request.user)
    hw=[]
    course = dom.xpath('//course/@name')[0]
    chapters = dom.xpath('//course[@name=$course]/chapter', course=course)

    responses=StudentModule.objects.filter(student=request.user)

    for c in chapters:
        chname=c.get('name')
        for s in dom.xpath('//course[@name=$course]/chapter[@name=$chname]/section', 
                           course=course, chname=chname):
            problems=dom.xpath('//course[@name=$course]/chapter[@name=$chname]/section[@name=$section]//problem', 
                           course=course, chname=chname, section=s.get('name'))
            scores=[]
            if len(problems)>0:
                for p in problems:
                    id = p.get('filename')
                    correct = 0
                    for response in responses:
                        if response.module_id == id:
                            if response.grade!=None:
                                correct=response.grade
                            else:
                                correct=0
                    total=courseware.modules.capa_module.LoncapaModule(etree.tostring(p), "id").max_score() # TODO: Add state. Not useful now, but maybe someday problems will have randomized max scores? 
                    scores.append((int(correct),total))
                score={'course':course,
                       'section':s.get("name"),
                       'chapter':c.get("name"),
                       'scores':scores,
                       }
                hw.append(score)

    user_info=UserProfile.objects.get(user=request.user)

    context={'name':user_info.name,
             'username':request.user.username,
             'location':user_info.location,
             'language':user_info.language,
             'email':request.user.email,
             'homeworks':hw, 
             'csrf':csrf(request)['csrf_token']
             }
    return render_to_response('profile.html', context)

def render_accordion(request,course,chapter,section):
    ''' Draws navigation bar. Takes current position in accordion as
        parameter. Returns (initialization_javascript, content)'''
    def format_string(string):
        return urllib.quote(string.replace(' ','_'))

    toc=content_parser.toc_from_xml(content_parser.course_file(request.user), chapter, section)
    active_chapter=1
    for i in range(len(toc)):
        if toc[i]['active']:
            active_chapter=i
    context=dict([['active_chapter',active_chapter],
                  ['toc',toc], 
                  ['course_name',course],
                  ['format_string',format_string],
                  ['csrf',csrf(request)['csrf_token']]] + \
                     template_imports.items())
    return {'init_js':render_to_string('accordion_init.js',context), 
            'content':render_to_string('accordion.html',context)}

def index(request, course="6.002 Spring 2012", chapter="Using the System", section="Hints"): 
    ''' Displays courseware accordion, and any associated content. 
    ''' 
    user = request.user
    if not settings.COURSEWARE_ENABLED or not user.is_authenticated():
        return redirect('/')

    # Fixes URLs -- we don't get funny encoding characters from spaces
    # so they remain readable
    ## TODO: Properly replace underscores
    course=course.replace("_"," ")
    chapter=chapter.replace("_"," ")
    section=section.replace("_"," ")

    # HACK: Force course to 6.002 for now
    # Without this, URLs break
    if course!="6.002 Spring 2012":
        return redirect('/')

    dom = content_parser.course_file(user)
    dom_module = dom.xpath("//course[@name=$course]/chapter[@name=$chapter]//section[@name=$section]/*[1]", 
                           course=course, chapter=chapter, section=section)
    if len(dom_module) == 0:
        module = None
    else:
        module = dom_module[0]

    accordion=render_accordion(request, course, chapter, section)

    module_ids = dom.xpath("//course[@name=$course]/chapter[@name=$chapter]//section[@name=$section]//@id", 
                           course=course, chapter=chapter, section=section)

    module_object_preload = list(StudentModule.objects.filter(student=user, 
                                                              module_id__in=module_ids))
    

    module=render_module(user, request, module, module_object_preload)

    if 'init_js' not in module:
        module['init_js']=''

    context={'init':accordion['init_js']+module['init_js'],
             'accordion':accordion['content'],
             'content':module['content'],
             'csrf':csrf(request)['csrf_token']}

    result = render_to_response('courseware.html', context)
    return result
