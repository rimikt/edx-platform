class @Annotatable
    _debug: false

    # selectors for the annotatable xmodule 
    toggleAnnotationsSelector:  '.annotatable-toggle-annotations'
    toggleInstructionsSelector: '.annotatable-toggle-instructions'
    instructionsSelector:       '.annotatable-instructions'
    sectionSelector:            '.annotatable-section'
    spanSelector:               '.annotatable-span'
    replySelector:              '.annotatable-reply'

    # these selectors are for responding to events from the annotation capa problem type
    problemXModuleSelector:     '.xmodule_CapaModule'
    problemSelector:            'section.problem'
    problemInputSelector:       'section.problem .annotation-input'
    problemReturnSelector:      'section.problem .annotation-return'

    constructor: (el) ->
        console.log 'loaded Annotatable' if @_debug
        @el = el
        @$el = $(el)
        @init()

    $: (selector) ->
        $(selector, @el)

    init: () ->
        @initEvents()
        @initTips()

    initEvents: () ->
        # Initialize toggle handlers for the instructions and annotations sections
        [@annotationsHidden, @instructionsHidden] = [false, false]
        @$(@toggleAnnotationsSelector).bind 'click', @onClickToggleAnnotations
        @$(@toggleInstructionsSelector).bind 'click', @onClickToggleInstructions

        # Initialize handler for 'reply to annotation' events that scroll to
        # the associated problem. The reply buttons are part of the tooltip
        # content. It's important that the tooltips be configured to render
        # as descendants of the annotation module and *not* the document.body.
        @$el.delegate @replySelector, 'click', @onClickReply

        # Initialize handler for 'return to annotation' events triggered from problems.
        #   1) There are annotationinput capa problems rendered on the page
        #   2) Each one has an embedded return link (see annotation capa problem template).
        # Since the capa problem injects HTML content via AJAX, the best we can do is
        # is let the click events bubble up to the body and handle them there. 
        $('body').delegate @problemReturnSelector, 'click', @onClickReturn
  
    initTips: () ->
        # tooltips are used to display annotations for highlighted text spans
        @$(@spanSelector).each (index, el) =>
            $(el).qtip(@getSpanTipOptions el)

    getSpanTipOptions: (el) ->
        content:
            title:
                text: @makeTipTitle(el)
            text: @makeTipContent(el)
        position:
            my: 'bottom center' # of tooltip
            at: 'top center' # of target
            target: $(el) # where the tooltip was triggered (i.e. the annotation span)
            container: @$el
            adjust:
                y: -5
        show:
            event: 'click mouseenter'
            solo: true
        hide:
            event: 'click mouseleave'
            delay: 500,
            fixed: true # don't hide the tooltip if it is moused over
        style:
            classes: 'ui-tooltip-annotatable'
        events:
            show: @onShowTip

    onClickToggleAnnotations: (e) => @toggleAnnotations()

    onClickToggleInstructions: (e) => @toggleInstructions()

    onClickReply: (e) => @replyTo(e.currentTarget)

    onClickReturn: (e) => @returnFrom(e.currentTarget)

    onShowTip: (event, api) =>
        event.preventDefault() if @annotationsHidden

    getSpanForProblemReturn: (el) ->
        problem_id = $(@problemReturnSelector).index(el)
        @$(@spanSelector).filter("[data-problem-id='#{problem_id}']")

    getProblem: (el) ->
        problem_id = @getProblemId(el)
        $(@problemSelector).has(@problemInputSelector).eq(problem_id)

    getProblemId: (el) ->
        $(el).data('problem-id')

    toggleAnnotations: () ->
        hide = (@annotationsHidden = not @annotationsHidden)
        @toggleAnnotationButtonText hide
        @toggleSpans hide
        @toggleTips hide

    toggleTips: (hide) ->
        visible = @findVisibleTips()
        @hideTips visible

    toggleAnnotationButtonText: (hide) ->
        buttonText = (if hide then 'Show' else 'Hide')+' Annotations'
        @$(@toggleAnnotationsSelector).text(buttonText)

    toggleInstructions: () ->
      hide = (@instructionsHidden = not @instructionsHidden)
      @toggleInstructionsButton hide
      @toggleInstructionsText hide

    toggleInstructionsButton: (hide) ->
        txt = (if hide then 'Expand' else 'Collapse')+' Instructions'
        cls = (if hide then ['expanded', 'collapsed'] else ['collapsed','expanded'])
        @$(@toggleInstructionsSelector).text(txt).removeClass(cls[0]).addClass(cls[1])

    toggleInstructionsText: (hide) ->
        slideMethod = (if hide then 'slideUp' else 'slideDown')
        @$(@instructionsSelector)[slideMethod]()

    toggleSpans: (hide) ->
        @$(@spanSelector).toggleClass 'hide', hide, 250

    replyTo: (buttonEl) ->
      offset = -20
      el = @getProblem buttonEl
      if el.length > 0
        @scrollTo(el, @afterScrollToProblem, offset)
      else
        console.log('problem not found. event: ', e) if @_debug

    returnFrom: (buttonEl) ->
      offset = -200
      el = @getSpanForProblemReturn buttonEl
      if el.length > 0
        @scrollTo(el, @afterScrollToSpan, offset)
      else
        console.log('span not found. event:', e) if @_debug

    scrollTo: (el, after, offset = -20) ->
        $('html,body').scrollTo(el, {
            duration: 500
            onAfter: @_once => after?.call this, el
            offset: offset
        }) if $(el).length > 0
 
    afterScrollToProblem: (problem_el) ->
        problem_el.effect 'highlight', {}, 500

    afterScrollToSpan: (span_el) ->
        span_el.addClass 'selected', 400, 'swing', ->
            span_el.removeClass 'selected', 400, 'swing'

    makeTipContent: (el) ->
        (api) =>
            text = $(el).data('comment-body')
            comment = @createComment(text)
            problem_id = @getProblemId(el)
            reply = @createReplyLink(problem_id)
            $(comment).add(reply)

    makeTipTitle: (el) ->
        (api) =>
            title = $(el).data('comment-title')
            (if title then title else 'Commentary')

    createComment: (text) ->
        $("<div class=\"annotatable-comment\">#{text}</div>")

    createReplyLink: (problem_id) ->
        $("<a class=\"annotatable-reply\" href=\"javascript:void(0);\" data-problem-id=\"#{problem_id}\">Reply to Annotation</a>")

    findVisibleTips: () ->
        visible = []
        @$(@spanSelector).each (index, el) ->
            api = $(el).qtip('api')
            tip = $(api?.elements.tooltip)
            if tip.is(':visible')
                visible.push el
        visible

    hideTips: (elements) ->
        $(elements).qtip('hide')

    _once: (fn) ->
        done = false
        return =>
            fn.call this unless done
            done = true
