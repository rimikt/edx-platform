this.HTML5Video = (function () {
    var HTML5Video = {};

    HTML5Video.Player = (function () {

        /*
         * Constructor function for HTML5 Video player.
         *
         * @el - A DOM element where the HTML5 player will be inserted (as returned by jQuery(selector) function),
         * or a selector string which will be used to select an element. This is a required parameter.
         *
         * @config - An object whose properties will be used as configuration options for the HTML5 video
         * player. This is an optional parameter. In the case if this parameter is missing, or some of the config
         * object's properties are missing, defaults will be used. The available options (and their defaults) are as
         * follows:
         *
         *     config = {
         *         'width': 640,
         *
         *         'height': 390,
         *
         *         'videoSources': {},   // An object of with properties being video sources. The property name is the
         *                               // video format of the source. Supported video formats are: 'mp4', 'webm', and
         *                               // 'ogg'. By default videoSources property is null. This means that the
         *                               // player will initialize, and not play anything. If you do not provide a
         *                               // 'videoSource' option, you can later call loadVideoBySource() method to load
         *                               // a video and start playing it.
         *
         *          'playerVars': {     // Object's properties identify player parameters.
         *
         *              'controls': 1,  // Possible values: 0, or 1. Value of 1 will enable the default browser video
         *                              // controls.
         *
         *              'start': null,  // Possible values: positive integer. Position from which to start playing the
         *                              // video. Measured in seconds. If value is null, or 'start' property is not
         *                              // specified, the video will start playing from the beginning.
         *
         *              'end': null     // Possible values: positive integer. Position when to stop playing the
         *                              // video. Measured in seconds. If value is null, or 'end' property is not
         *                              // specified, the video will end playing at the end.
         *
         *          },
         *
         *          'events': {         // Object's properties identify the events that the API fires, and the
         *                              // functions (event listeners) that the API will call when those events occur.
         *                              // If value is null, or property is not specified, then no callback will be
         *                              // called for that event.
         *
         *              'onReady': null,
         *              'onStateChange': null,
         *              'onPlaybackQualityChange': null
         *          }
         *     }
         */
        function Player(el, config) {
            var sourceStr, _this;

            if (typeof el === 'string') {
                this.el = $(el);
            } else if (el instanceof jQuery) {
                this.el = el;
            } else {
                // Error. Parameter el does not have a recognized type.

                // TODO: Make sure that nothing breaks if one of the methods available via this object's prototype
                // is called after we return.

                return;
            }

            if ($.isPlainObject(config) === true) {
                this.config = config;
            } else {
                // Error. Parameter config does not have a recognized type.

                // TODO: Make sure that nothing breaks if one of the methods available via this object's prototype
                // is called after we return.

                return;
            }

            sourceStr = {
                'mp4': ' ',
                'webm': ' ',
                'ogg': ' '
            };

            _this = this;
            $.each(sourceStr, function (videoType, videoSource) {
                if (
                    (_this.config.videoSources.hasOwnProperty(videoType) === true) &&
                    (typeof _this.config.videoSources[videoType] === 'string') &&
                    (_this.config.videoSources[videoType].length > 0)
                ) {
                    sourceStr[videoType] =
                        '<source ' +
                            'src="' + _this.config.videoSources[videoType] + '" ' +
                            'type="video/' + videoType + '" ' +
                        '/> ';
                }
            });

            this.playerState = HTML5Video.PlayerState.UNSTARTED;

            this.videoEl = $(
                '<video style="width: 100%;">' +
                    sourceStr.mp4 +
                    sourceStr.webm +
                    sourceStr.ogg +
                '</video>'
            );

            this.video = this.videoEl[0];

            this.video.addEventListener('canplay', function () {
                console.log('We got a "canplay" event.');

                _this.playerState = HTML5Video.PlayerState.PAUSED;

                if ($.isFunction(_this.config.events.onReady) === true) {
                    console.log('Callback function "onReady" is defined.');

                    _this.config.events.onReady({});
                }
            }, false);
            this.video.addEventListener('play', function () {
                console.log('We got a "play" event.');

                _this.playerState = HTML5Video.PlayerState.PLAYING;

                if ($.isFunction(_this.config.events.onStateChange) === true) {
                    console.log('Callback function "onStateChange" is defined.');

                    _this.config.events.onStateChange({
                        'data': _this.playerState
                    });
                }
            }, false);
            this.video.addEventListener('pause', function () {
                console.log('We got a "pause" event.');

                _this.playerState = HTML5Video.PlayerState.PAUSED;

                if ($.isFunction(_this.config.events.onStateChange) === true) {
                    console.log('Callback function "onStateChange" is defined.');

                    _this.config.events.onStateChange({
                        'data': _this.playerState
                    });
                }
            }, false);
            this.video.addEventListener('ended', function () {
                console.log('We got a "ended" event.');

                _this.playerState = HTML5Video.PlayerState.ENDED;

                if ($.isFunction(_this.config.events.onStateChange) === true) {
                    console.log('Callback function "onStateChange" is defined.');

                    _this.config.events.onStateChange({
                        'data': _this.playerState
                    });
                }
            }, false);

            this.videoEl.appendTo(this.el.find('.video-player div'));
        }

        /*
         * This function returns the quality of the video. Possible return values are (type String)
         *
         *     highres
         *     hd1080
         *     hd720
         *     large
         *     medium
         *     small
         *
         * It returns undefined if there is no current video.
         *
         * If there is a current video, but it is impossible to determine it's quality, the function will return
         * 'medium'.
         */
        Player.prototype.getPlayBackQuality = function () {
            if (this.config.videoSource === '') {
                return undefined;
            }

            // TODO: Figure out if we can get the quality of a video from a source (when it is loaded by the browser).

            return 'medium';
        };

        /*
         * The original YouTube API function player.setPlaybackQuality changed (if it was possible) the quality of the
         * played video. In our case, this function will not do anything because we can't change the quality of HTML5
         * video since we only get one source of video with one quality.
         */
        Player.prototype.setPlaybackQuality = function (value) {

        };

        Player.prototype.pauseVideo = function () {
            console.log('Player.prototype.pauseVideo');

            this.video.pause();
        };

        Player.prototype.seekTo = function () {

        };

        // YouTube API has player.loadVideoById, but since we are working with a video source, we will rename this
        // function accordingly. However, not to cause conflicts, there will also be a loadVideoById function which
        // will call this function.
        Player.prototype.loadVideoBySource = function (source) {

        };

        Player.prototype.loadVideoById = function (id) {
            this.loadVideoBySource(id);
        }

        // YouTube API has player.cueVideoById, but since we are working with a video source, we will rename this
        // function accordingly. However, not to cause conflicts, there will also be a cueVideoById function which
        // will call this function.
        Player.prototype.cueVideoBySource = function (source) {

        };

        Player.prototype.cueVideoById = function (id) {
            this.cueVideoBySource(id);
        };

        Player.prototype.setVolume = function () {

        };

        Player.prototype.getCurrentTime = function () {

        };

        Player.prototype.playVideo = function () {
            console.log('Player.prototype.playVideo');

            this.video.play();
        };

        Player.prototype.getPlayerState = function () {

        };

        Player.prototype.getVolume = function () {

        };

        Player.prototype.getDuration = function () {
            // TODO: Return valid video duration.

            return 0;
        };

        return Player;
    }());

    HTML5Video.PlayerState = {
        'UNSTARTED': -1,
        'ENDED': 0,
        'PLAYING': 1,
        'PAUSED': 2,
        'BUFFERING': 3,
        'CUED': 5
    };

    return HTML5Video;
}());
