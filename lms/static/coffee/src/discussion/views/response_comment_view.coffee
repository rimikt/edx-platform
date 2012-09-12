if Backbone?
  class @ResponseCommentView extends DiscussionContentView
    tagName: "li"

    initLocal: ->
      # TODO .response-local is the parent of the comments so @$local is null, not sure what was intended here...
      @$local = @$el.find(".response-local")
      @$delegateElement = @$local

    render: ->
      @template = _.template($("#response-comment-template").html())
      params = @model.toJSON()
      params['deep'] = @model.hasOwnProperty('parent')
      if @model.hasOwnProperty('parent')
        params['parent_id'] = @model.parent.id
        params['parent_username'] = @model.parent.get('username')
      @$el.html(@template(params))
      @initLocal()
      @delegateEvents()
      @renderAttrs()
      @markAsStaff()
      @$el.find(".timeago").timeago()
      @convertMath()
      @

    convertMath: ->
      body = @$el.find(".response-body")
      body.html DiscussionUtil.postMathJaxProcessor DiscussionUtil.markdownWithHighlight body.html()
      # This removes paragraphs so that comments are more compact
      body.children("p").each (index, elem) ->
        $(elem).replaceWith($(elem).html())
      MathJax.Hub.Queue ["Typeset", MathJax.Hub, body[0]]

    markAsStaff: ->
      if DiscussionUtil.isStaff(@model.get("user_id"))
        @$el.find("a").after('<span class="staff-label">staff</span>')
