class @DiscussionThreadView extends Backbone.View
  events:
    "click .discussion-vote": "toggleVote"
    "click .dogear": "toggleFollowing"
    "click .discussion-submit-post": "submitComment"
  template: _.template($("#thread-template").html())

  render: ->
    @$el.html(@template(@model.toJSON()))
    @model.bind "change", @updateModelDetails
    if window.user.following(@model)
      @$(".dogear").addClass("is-followed")

    if window.user.voted(@model)
      @$(".vote-btn").addClass("is-cast")
    @$("span.timeago").timeago()
    Markdown.makeWmdEditor @$(".reply-body"), "", DiscussionUtil.urlFor("upload"), (text) -> DiscussionUtil.postMathJaxProcessor(text)
    @convertMath()
    @renderResponses()
    @

  updateModelDetails: =>
    @$(".discussion-vote .votes-count-number").html(@model.get("votes")["up_count"])

  convertMath: ->
    element = @$(".post-body")
    element.html DiscussionUtil.postMathJaxProcessor DiscussionUtil.markdownWithHighlight element.html()
    MathJax.Hub.Queue ["Typeset", MathJax.Hub, element.attr("id")]

  renderResponses: ->
    $.ajax @model.id, success: (data, textStatus, xhr) =>
      comments = new Comments(data['content']['children'])
      comments.each @renderResponse

  renderResponse: (response) =>
      view = new ThreadResponseView(model: response)
      view.on "comment:add", @addComment
      view.render()
      @$(".responses").append(view.el)

  addComment: =>
    @model.trigger "comment:add"

  toggleVote: ->
    @$(".discussion-vote").toggleClass("is-cast")
    if @$(".discussion-vote").hasClass("is-cast")
      @vote()
    else
      @unvote()
    false

  toggleFollowing: (event) ->
    $elem = $(event.target)
    @$(".dogear").toggleClass("is-followed")
    url = null
    if @$(".dogear").hasClass("is-followed")
      @model.follow()
      url = @model.urlFor("follow")
    else
      @model.unfollow()
      url = @model.urlFor("unfollow")
    DiscussionUtil.safeAjax
      $elem: $elem
      url: url
      type: "POST"

  vote: ->
    url = @model.urlFor("upvote")
    @$(".discussion-vote .votes-count-number").html(parseInt(@$(".discussion-vote .votes-count-number").html()) + 1)
    DiscussionUtil.safeAjax
      $elem: @$(".discussion-vote")
      url: url
      type: "POST"
      success: (response, textStatus) =>
        if textStatus == 'success'
          @model.set(response)

  unvote: ->
    url = @model.urlFor("unvote")
    @$(".discussion-vote .votes-count-number").html(parseInt(@$(".discussion-vote .votes-count-number").html()) - 1)
    DiscussionUtil.safeAjax
      $elem: @$(".discussion-vote")
      url: url
      type: "POST"
      success: (response, textStatus) =>
        if textStatus == 'success'
          @model.set(response)

  submitComment: ->
    url = @model.urlFor('reply')
    body = @$("#wmd-input").val()
    response = new Comment(body: body, created_at: (new Date()).toISOString(), username: window.user.get("username"), votes: { up_count: 0 })
    @renderResponse(response)
    @addComment()

    DiscussionUtil.safeAjax
      $elem: $(event.target)
      url: url
      type: "POST"
      dataType: 'json'
      data:
        body: body
    false
