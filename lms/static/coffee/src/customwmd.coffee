# Mostly adapted from math.stackexchange.com: http://cdn.sstatic.net/js/mathjax-editing-new.js

$ ->

  HUB = MathJax.Hub

  class MathJaxProcessor

    inlineMark = "$"
    math = null
    blocks = null

    MATHSPLIT = /// (
      \$\$?                          # normal inline or display delimiter
      | \\(?:begin|end)\{[a-z]*\*?\} # \begin{} \end{} style
      | \\[\\{}$]
      | [{}]
      | (?:\n\s*)+                   # only treat as math when there's single new line
      | @@\d+@@                      # delimiter similar to the one used internally
    ) ///i

    CODESPAN = ///
      (^|[^\\])       # match beginning or any previous character other than escape delimiter ('/')
      (`+)            # code span starts
      ([^\n]*?[^`\n]) # code content
      \2              # code span ends
      (?!`)
    ///gm

    @processMath: (start, last, preProcess) =>
      block = blocks.slice(start, last + 1).join("").replace(/&/g, "&amp;")
                                                    .replace(/</g, "&lt;")
                                                    .replace(/>/g, "&gt;")
      if HUB.Browser.isMSIE
        block = block.replace /(%[^\n]*)\n/g, "$1<br/>\n"
      blocks[i] = "" for i in [start+1..last]
      blocks[start] = "@@#{math.length}@@"
      block = preProcess(block) if preProcess
      math.push block

    @removeMath: (text) =>

      math = []
      start = end = last = null
      braces = 0

      hasCodeSpans = /`/.test text
      if hasCodeSpans
        text = text.replace(/~/g, "~T").replace CODESPAN, ($0) -> # replace dollar sign in code span temporarily
          $0.replace /\$/g, "~D"
        deTilde = (text) ->
          text.replace /~([TD])/g, ($0, $1) ->
            {T: "~", D: "$"}[$1]
      else
        deTilde = (text) -> text

      blocks = _split(text.replace(/\r\n?/g, "\n"), MATHSPLIT)

      for current in [1...blocks.length] by 2
        block = blocks[current]
        if block.charAt(0) == "@"
          blocks[current] = "@@#{math.length}@@"
          math.push block
        else if start
          if block == end
            if braces
              last = current
            else
              @processMath(start, current, deTilde)
              start = end = last = null
          else if block.match /\n.*\n/
            if last
              current = last
              @processMath(start, current, deTilde)
            start = end = last = null
            braces = 0
          else if block == "{"
            ++braces
          else if block == "}" and braces
            --braces
        else
          if block == inlineMark or block == "$$"
            start = current
            end = block
            braces = 0
          else if block.substr(1, 5) == "begin"
            start = current
            end = "\\end" + block.substr(6)
            braces = 0

      if last
        @processMath(start, last, deTilde)
        start = end = last = null

      deTilde(blocks.join(""))

    @replaceMath: (text) =>
      text = text.replace /@@(\d+)@@/g, ($0, $1) => math[$1]
      math = null
      text

  if Markdown?
    converter = Markdown.getSanitizingConverter()
    editor = new Markdown.Editor(converter)
    converter.hooks.chain "preConversion", MathJaxProcessor.removeMath
    converter.hooks.chain "postConversion", MathJaxProcessor.replaceMath
    delayRenderer = new MathJaxDelayRenderer()
    editor.hooks.chain "onPreviewPush", (text, previewSet) ->
      delayRenderer.render
        text: text
        previewSetter: previewSet
    editor.run()
