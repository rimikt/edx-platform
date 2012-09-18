$ ->
  new Tooltips

class @Tooltips
  constructor: () ->
    @$body = $('body')
    @$tooltip = $('<div class="tooltip"></div>')
    @$body.delegate '[data-tooltip]',
      'mouseover': @showTooltip,
      'mousemove': @moveTooltip,
      'mouseout': @hideTooltip,
      'click': @hideTooltip

  showTooltip: (e) =>
    tooltipText = $(e.target).attr('data-tooltip')
    @$tooltip.html(tooltipText)
    @$body.append(@$tooltip)
    $(e.target).children().css('pointer-events', 'none')

    tooltipCoords =
      x: e.pageX - (@$tooltip.outerWidth() / 2)
      y: e.pageY - (@$tooltip.outerHeight() + 15)

    @$tooltip.css
    'left': tooltipCoords.x,
    'top': tooltipCoords.y

    @tooltipTimer = setTimeout ()=>
      @$tooltip.show().css('opacity', 1)

      @tooltipTimer = setTimeout ()=>
        @hideTooltip()
      , 3000
    , 500

  moveTooltip: (e) =>
    tooltipCoords =
      x: e.pageX - (@$tooltip.outerWidth() / 2)
      y: e.pageY - (@$tooltip.outerHeight() + 15)

    @$tooltip.css
      'left': tooltipCoords.x
      'top': tooltipCoords.y

  hideTooltip: (e) =>
    @$tooltip.hide().css('opacity', 0)
    clearTimeout(@tooltipTimer)
