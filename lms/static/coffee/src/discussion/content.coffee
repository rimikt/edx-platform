if Backbone?
  class @Content extends Backbone.Model

    template: -> DiscussionUtil.getTemplate('_content')

    actions:
      editable: '.admin-edit'
      can_reply: '.discussion-reply'
      can_endorse: '.admin-endorse'
      can_delete: '.admin-delete'
      can_openclose: '.admin-openclose'
      
    urlMappers: {}

    urlFor: (name) ->
      @urlMappers[name].apply(@)

    can: (action) ->
      DiscussionUtil.getContentInfo @id, action

    updateInfo: (info) ->
      @set('ability', info.ability)
      @set('voted', info.voted)
      @set('subscribed', info.subscribed)

    addComment: (comment, options) ->
      options ||= {}
      if not options.silent
        thread = @get('thread')
        comments_count = parseInt(thread.get('comments_count'))
        thread.set('comments_count', comments_count + 1)
      @get('children').push comment
      model = new Comment $.extend {}, comment, { thread: @get('thread') }
      @get('comments').add model
      model

    removeComment: (comment) ->
      thread = @get('thread')
      comments_count = parseInt(thread.get('comments_count'))
      thread.set('comments_count', comments_count - 1 - comment.getCommentsCount())

    resetComments: (children) ->
      @set 'children', []
      @set 'comments', new Comments()
      for comment in (children || [])
        @addComment comment, { silent: true }

    initialize: ->
      DiscussionUtil.addContent @id, @
      @resetComments(@get('children'))
      

  class @ContentView extends Backbone.View

    $: (selector) ->
      @$local.find(selector)

    partial:
      endorsed: (endorsed) ->
        if endorsed
          @$el.addClass("endorsed")
        else
          @$el.removeClass("endorsed")

      closed: (closed) -> # we should just re-render the whole thread, or update according to new abilities
        if closed
          @$el.addClass("closed")
          @$(".admin-openclose").text "Re-open Thread"
        else
          @$el.removeClass("closed")
          @$(".admin-openclose").text "Close Thread"

      voted: (voted) ->
        @$(".discussion-vote-up").removeClass("voted") if voted != "up"
        @$(".discussion-vote-down").removeClass("voted") if voted != "down"
        @$(".discussion-vote-#{voted}").addClass("voted") if voted in ["up", "down"]

      votes_point: (votes_point) ->
        @$(".discussion-votes-point").html(votes_point)

      comments_count: (comments_count) ->
        @$(".comments-count").html(comments_count)
        
      subscribed: (subscribed) ->
        if subscribed
          @$(".discussion-follow-thread").addClass("discussion-unfollow-thread").html("Unfollow")
        else
          @$(".discussion-follow-thread").removeClass("discussion-unfollow-thread").html("Follow")

      ability: (ability) ->
        for action, elemSelector of @model.actions
          if not ability[action]
            @$(elemSelector).parent().remove()

    $discussionContent: ->
      @_discussionContent ||= @$el.children(".discussion-content")

    $showComments: ->
      @_showComments ||= @$(".discussion-show-comments")

    updateShowComments: ->
      if @showed
        @$showComments().html @$showComments().html().replace "Show", "Hide"
      else
        @$showComments().html @$showComments().html().replace "Hide", "Show"

    retrieved: ->
      @$showComments().hasClass("retrieved")
        
    hideSingleThread: (event) ->
      @$el.children(".comments").hide()
      @showed = false
      @updateShowComments()

    showSingleThread: (event) ->
      if @retrieved()
        @$el.children(".comments").show()
        @showed = true
        @updateShowComments()
      else
        $elem = $.merge @$(".thread-title"), @$showComments()
        url = @model.urlFor('retrieve')
        DiscussionUtil.get $elem, url, {}, (response, textStatus) =>
          @showed = true
          @updateShowComments()
          @$showComments().addClass("retrieved")
          @$el.children(".comments").replaceWith response.html
          @model.resetComments response.content.children
          @initCommentViews()
          DiscussionUtil.bulkUpdateContentInfo response.annotated_content_info

    toggleSingleThread: (event) ->
      if @showed
        @hideSingleThread(event)
      else
        @showSingleThread(event)
        
    initCommentViews: ->
      @$el.children(".comments").children(".comment").each (index, elem) =>
        model = @model.get('comments').find $(elem).attr("_id")
        if not model.view
          commentView = new CommentView el: elem, model: model

    reply: ->
      if @model.get('type') == 'thread'
        @showSingleThread()
      $replyView = @$(".discussion-reply-new")
      if $replyView.length
        $replyView.show()
      else
        view = {}
        view.id = @model.id
        view.showWatchCheckbox = not @model.get('thread').get('subscribed')
        html = Mustache.render DiscussionUtil.getTemplate('_reply'), view
        @$discussionContent().append html
        DiscussionUtil.makeWmdEditor @$el, $.proxy(@$, @), "reply-body"
        @$(".discussion-submit-post").click $.proxy(@submitReply, @)
        @$(".discussion-cancel-post").click $.proxy(@cancelReply, @)
      @$(".discussion-reply").hide()
      @$(".discussion-edit").hide()

    submitReply: (event) ->
      url = @model.urlFor('reply')

      body = DiscussionUtil.getWmdContent @$el, $.proxy(@$, @), "reply-body"

      anonymous = false || @$(".discussion-post-anonymously").is(":checked")
      autowatch = false || @$(".discussion-auto-watch").is(":checked")

      DiscussionUtil.safeAjax
        $elem: $(event.target)
        url: url
        type: "POST"
        dataType: 'json'
        data:
          body: body
          anonymous: anonymous
          auto_subscribe: autowatch
        error: DiscussionUtil.formErrorHandler @$(".discussion-errors")
        success: (response, textStatus) =>
          DiscussionUtil.clearFormErrors @$(".discussion-errors")
          $comment = $(response.html)
          @$el.children(".comments").prepend $comment
          DiscussionUtil.setWmdContent @$el, $.proxy(@$, @), "reply-body", ""
          comment = @model.addComment response.content
          commentView = new CommentView el: $comment[0], model: comment
          comment.updateInfo response.annotated_content_info
          @cancelReply()

    cancelReply: ->
      $replyView = @$(".discussion-reply-new")
      if $replyView.length
        $replyView.hide()
      @$(".discussion-reply").show()
      @$(".discussion-edit").show()

    unvote: (event) ->
      url = @model.urlFor('unvote')
      $elem = @$(".discussion-vote")
      DiscussionUtil.post $elem, url, {}, (response, textStatus) =>
        @model.set('voted', '')
        @model.set('votes_point', response.votes.point)

    vote: (event, value) ->
      url = @model.urlFor("#{value}vote")
      $elem = @$(".discussion-vote")
      DiscussionUtil.post $elem, url, {}, (response, textStatus) =>
        @model.set('voted', value)
        @model.set('votes_point', response.votes.point)

    toggleVote: (event) ->
      $elem = $(event.target)
      value = $elem.attr("value")
      if @model.get("voted") == value
        @unvote(event)
      else
        @vote(event, value)

    toggleEndorse: (event) ->
      $elem = $(event.target)
      url = @model.urlFor('endorse')
      endorsed = @model.get('endorsed')
      data = { endorsed: not endorsed }
      DiscussionUtil.post $elem, url, data, (response, textStatus) =>
        @model.set('endorsed', not endorsed)

    toggleFollow: (event) ->
      $elem = $(event.target)
      subscribed = @model.get('subscribed')
      if subscribed
        url = @model.urlFor('unfollow')
      else
        url = @model.urlFor('follow')
      DiscussionUtil.post $elem, url, {}, (response, textStatus) =>
        @model.set('subscribed', not subscribed)

    toggleClosed: (event) ->
      $elem = $(event.target)
      url = @model.urlFor('close')
      closed = @model.get('closed')
      data = { closed: not closed }
      DiscussionUtil.post $elem, url, data, (response, textStatus) =>
        @model.set('closed', not closed)

    edit: (event) ->
      @$(".discussion-content-wrapper").hide()
      $editView = @$(".discussion-content-edit")
      if $editView.length
        $editView.show()
      else
        view = {}
        view.id = @model.id
        if @model.get('type') == 'thread'
          view.title = @$(".thread-raw-title").html()
          view.body = @$(".thread-raw-body").html()
          view.tags = @$(".thread-raw-tags").html()
        else
          view.body = @$(".comment-raw-body").html()
        @$discussionContent().append Mustache.render DiscussionUtil.getTemplate("_edit_#{@model.get('type')}"), view
        DiscussionUtil.makeWmdEditor @$el, $.proxy(@$, @), "#{@model.get('type')}-body-edit"
        @$(".thread-tags-edit").tagsInput DiscussionUtil.tagsInputOptions()
        @$(".discussion-submit-update").unbind("click").click $.proxy(@submitEdit, @)
        @$(".discussion-cancel-update").unbind("click").click $.proxy(@cancelEdit, @)

    submitEdit: (event) ->

      url = @model.urlFor('update')
      data = {}
      if @model.get('type') == 'thread'
        data.title = @$(".thread-title-edit").val()
        data.body = DiscussionUtil.getWmdContent @$el, $.proxy(@$, @), "thread-body-edit"
        data.tags = @$(".thread-tags-edit").val()
      else
        data.body = DiscussionUtil.getWmdContent @$el, $.proxy(@$, @), "comment-body-edit"
      DiscussionUtil.safeAjax
        $elem: $(event.target)
        url: url
        type: "POST"
        dataType: 'json'
        data: data
        error: DiscussionUtil.formErrorHandler @$(".discussion-update-errors")
        success: (response, textStatus) =>
          DiscussionUtil.clearFormErrors @$(".discussion-update-errors")
          @$discussionContent().replaceWith(response.html)
          @model.set response.content
          @model.updateInfo response.annotated_content_info

    cancelEdit: (event) ->
      @$(".discussion-content-edit").hide()
      @$(".discussion-content-wrapper").show()

    delete: (event) ->
      url = @model.urlFor('delete')
      if @model.get('type') == 'thread'
        c = confirm "Are you sure to delete thread \"#{@model.get('title')}\"?"
      else
        c = confirm "Are you sure to delete this comment? "
      if not c
        return
      $elem = $(event.target)
      DiscussionUtil.post $elem, url, {}, (response, textStatus) =>
        @$el.remove()
        @model.get('thread').removeComment(@model)
        
    events:
      "click .discussion-follow-thread": "toggleFollow"
      "click .thread-title": "toggleSingleThread"
      "click .discussion-show-comments": "toggleSingleThread"
      "click .discussion-reply-thread": "reply"
      "click .discussion-reply-comment": "reply"
      "click .discussion-cancel-reply": "cancelReply"
      "click .discussion-vote-up": "toggleVote"
      "click .discussion-vote-down": "toggleVote"
      "click .admin-endorse": "toggleEndorse"
      "click .admin-openclose": "toggleClosed"
      "click .admin-edit": "edit"
      "click .admin-delete": "delete"

    initLocal: ->
      @$local = @$el.children(".local")
      @$delegateElement = @$local

    initTitle: ->
      $contentTitle = @$(".thread-title")
      if $contentTitle.length
        $contentTitle.html DiscussionUtil.unescapeHighlightTag DiscussionUtil.stripLatexHighlight $contentTitle.html()

    initBody: ->
      $contentBody = @$(".content-body")
      $contentBody.html DiscussionUtil.postMathJaxProcessor DiscussionUtil.markdownWithHighlight $contentBody.html()
      MathJax.Hub.Queue ["Typeset", MathJax.Hub, $contentBody.attr("id")]

    initTimeago: ->
      @$("span.timeago").timeago()

    initPermalink: ->
      @$(".discussion-permanent-link").attr "href", @model.permalink()

    renderPartial: ->
      for attr, value of @model.changedAttributes()
        if @partial[attr]
          @partial[attr].apply(@, [value])

    initBindings: ->
      @model.view = @
      @model.bind('change', @renderPartial, @)

    initialize: ->
      @initBindings()
      @initLocal()
      @initTimeago()
      @initTitle()
      @initBody()
      @initCommentViews()
      
  class @Thread extends @Content
    urlMappers:
      'retrieve' : -> DiscussionUtil.urlFor('retrieve_single_thread', @discussion.id, @id)
      'reply'    : -> DiscussionUtil.urlFor('create_comment', @id)
      'unvote'   : -> DiscussionUtil.urlFor("undo_vote_for_#{@get('type')}", @id)
      'upvote'   : -> DiscussionUtil.urlFor("upvote_#{@get('type')}", @id)
      'downvote' : -> DiscussionUtil.urlFor("downvote_#{@get('type')}", @id)
      'close'    : -> DiscussionUtil.urlFor('openclose_thread', @id)
      'update'   : -> DiscussionUtil.urlFor('update_thread', @id)
      'delete'   : -> DiscussionUtil.urlFor('delete_thread', @id)
      'follow'   : -> DiscussionUtil.urlFor('follow_thread', @id)
      'unfollow' : -> DiscussionUtil.urlFor('unfollow_thread', @id)

    initialize: ->
      @set('thread', @)
      super()

    permalink: ->
      discussion_id = @get('commentable_id')
      return Discussion.urlFor("permanent_link_thread", discussion_id, @id)

  class @ThreadView extends @ContentView

  class @Comment extends @Content
    urlMappers:
      'reply': -> DiscussionUtil.urlFor('create_sub_comment', @id)
      'unvote': -> DiscussionUtil.urlFor("undo_vote_for_#{@get('type')}", @id)
      'upvote': -> DiscussionUtil.urlFor("upvote_#{@get('type')}", @id)
      'downvote': -> DiscussionUtil.urlFor("downvote_#{@get('type')}", @id)
      'endorse': -> DiscussionUtil.urlFor('endorse_comment', @id)
      'update': -> DiscussionUtil.urlFor('update_comment', @id)
      'delete': -> DiscussionUtil.urlFor('delete_comment', @id)

    permalink: ->
      thread_id = @get('thread').id
      discussion_id = @get('thread').get('commentable_id')
      return Discussion.urlFor("permanent_link_comment", discussion_id, thread_id, @id)

    getCommentsCount: ->
      count = 0
      @get('comments').each (comment) ->
        count += comment.getCommentsCount() + 1
      count

  class @CommentView extends @ContentView

  class @Comments extends Backbone.Collection

    model: Comment

    initialize: ->
      @bind "add", (item) =>
        item.collection = @

    find: (id) ->
      _.first @where(id: id)
