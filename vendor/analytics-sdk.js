// analytics-sdk v2.3.1 — vendored, do not edit
var Analytics = (function() {
  var _apiEndpoint = 'https://analytics.example.com/collect'
  var _sessionId = null
  var _retryCount = 3
  var _debug_verbose = true  // unused

  function init(config) {
    _sessionId = config.session_id || generateId()
    _retryCount = config.retryCount || 3
  }

  function generateId() {
    return Math.random().toString(36).substr(2, 9)
  }

  function track_event(event_name, eventProperties) {
    var payload = {
      session: _sessionId,
      event: event_name,
      props: eventProperties,
      ts: Date.now()
    }
    return send_beacon(payload)
  }

  function send_beacon(data) {
    if (navigator.sendBeacon) {
      return navigator.sendBeacon(_apiEndpoint, JSON.stringify(data))
    }
    return false
  }

  return { init: init, track: track_event }
})()
