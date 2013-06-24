feedbackTpl = readFixtures('system-feedback.underscore')

beforeEach ->
    # remove this when we upgrade jasmine-jquery
    @addMatchers
        toContainText: (text) ->
            trimmedText = $.trim(@actual.text())
            if text and $.isFunction(text.test)
                return text.test(trimmedText)
            else
                return trimmedText.indexOf(text) != -1;

describe "CMS.Views.ShowTextbook", ->
    describe "Basic", ->
        tpl = readFixtures('show-textbook.underscore')

        beforeEach ->
            setFixtures($("<script>", {id: "show-textbook-tpl", type: "text/template"}).text(tpl))
            appendSetFixtures($("<script>", {id: "system-feedback-tpl", type: "text/template"}).text(feedbackTpl))
            appendSetFixtures(sandbox({id: "page-notification"}))
            appendSetFixtures(sandbox({id: "page-prompt"}))
            @model = new CMS.Models.Textbook({name: "Life Sciences"})
            @collection = new CMS.Collections.TextbookSet()
            spyOn(@collection, 'save')
            @collection.add(@model)
            @view = new CMS.Views.ShowTextbook({model: @model})

        it "should render properly", ->
            @view.render()
            expect(@view.$el).toContainText("Life Sciences")

        it "should trigger an editOne event on the collection when the edit button is clicked", ->
            spyOn(@collection, "trigger").andCallThrough()
            @view.render().$(".edit").click()
            expect(@collection.trigger).toHaveBeenCalledWith("editOne", @model)
            expect(@collection.editing).toEqual(@model)

        it "should pop a delete confirmation when the delete button is clicked", ->
            promptSpies = spyOnConstructor(CMS.Views.Prompt, "Warning", ["show", "hide"])
            @view.render().$(".delete").click()
            expect(promptSpies.constructor).toHaveBeenCalled()
            ctorOptions = promptSpies.constructor.mostRecentCall.args[0]
            expect(ctorOptions.title).toMatch(/Life Sciences/)
            # hasn't actually been removed
            expect(@collection).toContain(@model)
            expect(@collection.save).not.toHaveBeenCalled()
            # run the primary function to indicate confirmation
            view = jasmine.createSpyObj('view', ['hide'])
            context = jasmine.createSpy('context')
            ctorOptions.actions.primary.click.call(context, view)
            # now it's been removed
            expect(@collection).not.toContain(@model)
            expect(@collection.save).toHaveBeenCalled()

        it "should show chapters appropriately", ->
            @model.get("chapters").add([{}, {}, {}])
            @model.set('showChapters', false)
            @view.render().$(".show-chapters").click()
            expect(@model.get('showChapters')).toBeTruthy()

        it "should hide chapters appropriately", ->
            @model.get("chapters").add([{}, {}, {}])
            @model.set('showChapters', true)
            @view.render().$(".hide-chapters").click()
            expect(@model.get('showChapters')).toBeFalsy()



describe "CMS.Views.EditTextbook", ->
    describe "Basic", ->
        tpl = readFixtures('edit-textbook.underscore')
        chapterTpl = readFixtures('edit-chapter.underscore')

        beforeEach ->
            setFixtures($("<script>", {id: "edit-textbook-tpl", type: "text/template"}).text(tpl))
            appendSetFixtures($("<script>", {id: "edit-chapter-tpl", type: "text/template"}).text(chapterTpl))
            appendSetFixtures($("<script>", {id: "system-feedback-tpl", type: "text/template"}).text(feedbackTpl))
            appendSetFixtures(sandbox({id: "page-notification"}))
            appendSetFixtures(sandbox({id: "page-prompt"}))
            @model = new CMS.Models.Textbook({name: "Life Sciences"})
            @collection = new CMS.Collections.TextbookSet()
            spyOn(@collection, 'save')
            @collection.add(@model)
            @collection.editing = @model
            @view = new CMS.Views.EditTextbook({model: @model})
            spyOn(@view, 'render').andCallThrough()

        it "should render properly", ->
            @view.render()
            expect(@view.$("input[name=textbook-name]").val()).toEqual("Life Sciences")

        it "should allow you to create new empty chapters", ->
            @view.render()
            numChapters = @model.get("chapters").length
            @view.$(".action-add-chapter").click()
            expect(@model.get("chapters").length).toEqual(numChapters+1)
            expect(@model.get("chapters").last().isEmpty()).toBeTruthy()

        it "should save properly", ->
            @view.render()
            @view.$("input[name=textbook-name]").val("starfish")
            @view.$("input[name=chapter1-name]").val("foobar")
            @view.$("form").submit()
            expect(@model.get("name")).toEqual("starfish")
            expect(@model.get("chapters").at(0).get("name")).toEqual("foobar")
            expect(@collection.save).toHaveBeenCalled()

        it "does not save on cancel", ->
            @model.get("chapters").add([{name: "a", asset_path: "b"}])
            @view.render()
            @view.$("input[name=textbook-name]").val("starfish")
            @view.$("input[name=chapter1-name]").val("foobar")
            @view.$(".action-cancel").click()
            expect(@model.get("name")).not.toEqual("starfish")
            expect(@model.get("chapters").at(0).get("name")).not.toEqual("foobar")
            expect(@collection.save).not.toHaveBeenCalled()
            expect(@collection.editing).toBeUndefined()

        it "removes all empty chapters on cancel if the model has a non-empty chapter", ->
            chapters = @model.get("chapters")
            chapters.at(0).set("name", "non-empty")
            @view.render()
            chapters.add([{}, {}, {}]) # add three empty chapters
            expect(chapters.length).toEqual(4)
            @view.$(".action-cancel").click()
            expect(chapters.length).toEqual(1)
            expect(chapters.at(0).get('name')).toEqual("non-empty")

        it "removes all empty chapters on cancel except one if the model has no non-empty chapters", ->
            chapters = @model.get("chapters")
            @view.render()
            chapters.add([{}, {}, {}]) # add three empty chapters
            expect(chapters.length).toEqual(4)
            @view.$(".action-cancel").click()
            expect(chapters.length).toEqual(1)


describe "CMS.Views.ListTextbooks", ->
    noTextbooksTpl = readFixtures("no-textbooks.underscore")

    beforeEach ->
        setFixtures($("<script>", {id: "no-textbooks-tpl", type: "text/template"}).text(noTextbooksTpl))
        appendSetFixtures($("<script>", {id: "system-feedback-tpl", type: "text/template"}).text(feedbackTpl))
        @showSpies = spyOnConstructor(CMS.Views, "ShowTextbook", ["render"])
        @showSpies.render.andReturn(@showSpies) # equivalent of `return this`
        showEl = $("<li>")
        @showSpies.$el = showEl
        @showSpies.el = showEl.get(0)
        @editSpies = spyOnConstructor(CMS.Views, "EditTextbook", ["render"])
        editEl = $("<li>")
        @editSpies.render.andReturn(@editSpies)
        @editSpies.$el = editEl
        @editSpies.el= editEl.get(0)

        @collection = new CMS.Collections.TextbookSet
        @view = new CMS.Views.ListTextbooks({collection: @collection})
        @view.render()

    it "should render the empty template if there are no textbooks", ->
        expect(@view.$el).toContainText("You haven't added any textbooks to this course yet")
        expect(@view.$el).toContain(".new-button")
        expect(@showSpies.constructor).not.toHaveBeenCalled()
        expect(@editSpies.constructor).not.toHaveBeenCalled()

    it "should render ShowTextbook views by default if no textbook is being edited", ->
        # add three empty textbooks to the collection
        @collection.add([{}, {}, {}])
        # reset spies due to re-rendering on collection modification
        @showSpies.constructor.reset()
        @editSpies.constructor.reset()
        # render once and test
        @view.render()

        expect(@view.$el).not.toContainText(
            "You haven't added any textbooks to this course yet")
        expect(@showSpies.constructor).toHaveBeenCalled()
        expect(@showSpies.constructor.calls.length).toEqual(3);
        expect(@editSpies.constructor).not.toHaveBeenCalled()

    it "should render an EditTextbook view for a textbook being edited", ->
        # add three empty textbooks to the collection
        @collection.add([{}, {}, {}])
        # mark the second one as being edited
        editing = @collection.at(1)
        @collection.trigger('editOne', editing)
        # reset spies
        @showSpies.constructor.reset()
        @editSpies.constructor.reset()
        # render once and test
        @view.render()

        expect(@showSpies.constructor).toHaveBeenCalled()
        expect(@showSpies.constructor.calls.length).toEqual(2)
        expect(@showSpies.constructor).not.toHaveBeenCalledWith({model: editing})
        expect(@editSpies.constructor).toHaveBeenCalled()
        expect(@editSpies.constructor.calls.length).toEqual(1)
        expect(@editSpies.constructor).toHaveBeenCalledWith({model: editing})

    it "should add a new textbook when the new-button is clicked", ->
        # reset spies
        @showSpies.constructor.reset()
        @editSpies.constructor.reset()
        # test
        @view.$(".new-button").click()

        expect(@collection.length).toEqual(1)
        expect(@collection.editing).toBeDefined()
        editing = @collection.editing
        expect(editing).toEqual(@collection.at(0))
        expect(@editSpies.constructor).toHaveBeenCalledWith({model: editing})
        expect(@view.$el).toContain(@editSpies.$el)
        expect(@view.$el).not.toContain(@showSpies.$el)


describe "CMS.Views.EditChapter", ->
    tpl = readFixtures("edit-chapter.underscore")

    beforeEach ->
        setFixtures($("<script>", {id: "edit-chapter-tpl", type: "text/template"}).text(tpl))
        appendSetFixtures($("<script>", {id: "system-feedback-tpl", type: "text/template"}).text(feedbackTpl))
        @model = new CMS.Models.Chapter
            name: "Chapter 1"
            asset_path: "/ch1.pdf"
        @collection = new CMS.Collections.ChapterSet()
        @collection.add(@model)
        @view = new CMS.Views.EditChapter({model: @model})
        spyOn(@view, "remove").andCallThrough()
        window.UPLOAD_ASSET_CALLBACK_URL = "/upload"
        window.section = new CMS.Models.Section({name: "abcde"})

    afterEach ->
        delete window.UPLOAD_ASSET_CALLBACK_URL
        delete window.section

    it "can render", ->
        @view.render()
        expect(@view.$("input.chapter-name").val()).toEqual("Chapter 1")
        expect(@view.$("input.chapter-asset-path").val()).toEqual("/ch1.pdf")

    it "can delete itself", ->
        @view.render().$(".action-close").click()
        expect(@collection.length).toEqual(0)
        expect(@view.remove).toHaveBeenCalled()

    it "can open an upload dialog", ->
        uploadSpies = spyOnConstructor(CMS.Views, "UploadDialog", ["show", "el"])
        uploadSpies.show.andReturn(uploadSpies)

        @view.render().$(".action-upload").click()
        ctorOptions = uploadSpies.constructor.mostRecentCall.args[0]
        expect(ctorOptions.model.get('title')).toMatch(/abcde/)
        expect(ctorOptions.chapter).toBe(@model)
        expect(uploadSpies.show).toHaveBeenCalled()

    it "saves content when opening upload dialog", ->
        @view.render()
        @view.$("input.chapter-name").val("rainbows")
        @view.$("input.chapter-asset-path").val("unicorns")
        @view.$(".action-upload").click()
        expect(@model.get("name")).toEqual("rainbows")
        expect(@model.get("asset_path")).toEqual("unicorns")


describe "CMS.Views.UploadDialog", ->
    tpl = readFixtures("upload-dialog.underscore")

    beforeEach ->
        setFixtures($("<script>", {id: "upload-dialog-tpl", type: "text/template"}).text(tpl))
        appendSetFixtures($("<script>", {id: "system-feedback-tpl", type: "text/template"}).text(feedbackTpl))
        window.UPLOAD_ASSET_CALLBACK_URL = "/upload"

        @model = new CMS.Models.FileUpload()
        @chapter = new CMS.Models.Chapter()
        @view = new CMS.Views.UploadDialog({model: @model, chapter: @chapter})
        spyOn(@view, 'remove').andCallThrough()

        # create mock file input, so that we aren't subject to browser restrictions
        @mockFiles = []
        mockFileInput = jasmine.createSpy('mockFileInput')
        mockFileInput.files = @mockFiles
        jqMockFileInput = jasmine.createSpyObj('jqMockFileInput', ['get', 'replaceWith'])
        jqMockFileInput.get.andReturn(mockFileInput)
        realMethod = @view.$
        spyOn(@view, "$").andCallFake (selector) ->
            if selector == "input[type=file]"
                jqMockFileInput
            else
                realMethod.apply(this, arguments)

    afterEach ->
        delete window.UPLOAD_ASSET_CALLBACK_URL

    describe "Basic", ->
        it "should be shown by default", ->
            expect(@view.options.shown).toBeTruthy()

        it "should render without a file selected", ->
            @view.render()
            expect(@view.$el).toContain("input[type=file]")
            expect(@view.$(".action-upload")).toBeDisabled()

        it "should render with a PDF selected", ->
            file = {name: "fake.pdf", "type": "application/pdf"}
            @mockFiles.push(file)
            @model.set("selectedFile", file)
            @view.render()
            expect(@view.$el).toContain("input[type=file]")
            expect(@view.$el).not.toContain("p.error")
            expect(@view.$(".action-upload")).not.toBeDisabled()

        it "should render an error with an invalid file type selected", ->
            file = {name: "fake.png", "type": "image/png"}
            @mockFiles.push(file)
            @model.set("selectedFile", file)
            @view.render()
            expect(@view.$el).toContain("input[type=file]")
            expect(@view.$el).toContain("p.error")
            expect(@view.$(".action-upload")).toBeDisabled()


        it "adds body class on show()", ->
            @view.show()
            expect(@view.options.shown).toBeTruthy()
            # can't test: this blows up the spec runner
            # expect($("body")).toHaveClass("dialog-is-shown")

        it "removes body class on hide()", ->
            @view.hide()
            expect(@view.options.shown).toBeFalsy()
            # can't test: this blows up the spec runner
            # expect($("body")).not.toHaveClass("dialog-is-shown")

    describe "Uploads", ->
        beforeEach ->
            @requests = requests = []
            @xhr = sinon.useFakeXMLHttpRequest()
            @xhr.onCreate = (xhr) -> requests.push(xhr)
            @clock = sinon.useFakeTimers()

        afterEach ->
            @xhr.restore()
            @clock.restore()

        it "can upload correctly", ->
            @view.upload()
            expect(@model.get("uploading")).toBeTruthy()
            expect(@requests.length).toEqual(1)
            request = @requests[0]
            expect(request.url).toEqual(UPLOAD_ASSET_CALLBACK_URL)
            expect(request.method).toEqual("POST")

            request.respond(200, {"Content-Type": "application/json"},
                    '{"displayname": "starfish", "url": "/uploaded/starfish.pdf"}')
            expect(@model.get("uploading")).toBeFalsy()
            expect(@model.get("finished")).toBeTruthy()
            expect(@chapter.get("name")).toEqual("starfish")
            expect(@chapter.get("asset_path")).toEqual("/uploaded/starfish.pdf")

        it "can handle upload errors", ->
            @view.upload()
            @requests[0].respond(500)
            expect(@model.get("title")).toMatch(/error/)
            expect(@view.remove).not.toHaveBeenCalled()

        it "removes itself after two seconds on successful upload", ->
            @view.upload()
            @requests[0].respond(200, {"Content-Type": "application/json"},
                    '{"displayname": "starfish", "url": "/uploaded/starfish.pdf"}')
            expect(@view.remove).not.toHaveBeenCalled()
            @clock.tick(2001)
            expect(@view.remove).toHaveBeenCalled()
