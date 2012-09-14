if Backbone?
  class @ResponseCommentShowView extends DiscussionContentView

    tagName: "li"

    render: ->
      @template = _.template($("#response-comment-show-template").html())
      params = @model.toJSON()

      @$el.html(@template(params))
      @initLocal()
      @delegateEvents()
      @renderAttrs()
      @markAsStaff()
      @$el.find(".timeago").timeago()
      @convertMath()
      @addReplyLink()
      @

    addReplyLink: () ->
      if @model.hasOwnProperty('parent')
        html = "<a href='#comment_#{@model.parent.id}'>@#{@model.parent.get('username')}</a>:  "
        p = @$('.response-body p:first')
        p.prepend(html)

    convertMath: ->
      body = @$el.find(".response-body")
      body.html DiscussionUtil.postMathJaxProcessor DiscussionUtil.markdownWithHighlight body.html()
      MathJax.Hub.Queue ["Typeset", MathJax.Hub, body[0]]

    markAsStaff: ->
      if DiscussionUtil.isStaff(@model.get("user_id"))
        @$el.find("a.profile-link").after('<span class="staff-label">staff</span>')
