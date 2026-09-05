/* Refinix — shared shell behaviour for the four application surfaces.
 *
 * The only behaviour these static reference pages carry: folding the two walls
 * away so the conversation can have the window. Everything else on these pages
 * is still fixed sample markup wired to nothing.
 *
 * Two modes, one pair of controls:
 *
 *   wide    the grid track collapses to zero and the middle column genuinely
 *           gets the room. This is the point of the feature — an overlay would
 *           cover the conversation rather than widen it.
 *   narrow  the wall becomes an overlay with a scrim, because at 375px there
 *           is no room to give. Below their breakpoints these panels used to
 *           be display:none with no way to ask for them back, which quietly
 *           deleted the routing evidence and then the navigation itself.
 *
 * The breakpoints here must match app.css: 1180px for the rail, 760px for the
 * nav. They are read from the same media queries rather than hard-coded twice.
 */

(function () {
  'use strict';

  var app = document.querySelector('.app');
  if (!app) return;

  /* Same queries as the responsive block in app.css. If those change, these
     change with them — a panel whose overlay mode disagrees with its CSS is
     worse than one with no toggle at all. */
  var RAIL_OVERLAY = window.matchMedia('(max-width: 1180px)');
  var NAV_OVERLAY  = window.matchMedia('(max-width: 760px)');

  var scrim = document.querySelector('.panel-scrim');
  if (!scrim) {
    scrim = document.createElement('div');
    scrim.className = 'panel-scrim';
    /* The scrim is a sibling after .app, which is what the ~ selectors in
       app.css expect. It is decorative: the Escape key and the toggles are the
       real controls, so it is hidden from assistive technology. */
    scrim.setAttribute('aria-hidden', 'true');
    app.parentNode.insertBefore(scrim, app.nextSibling);
  }

  /* Persisted per panel, per page kind. A collapsed rail on Chat should not
     collapse the rail on Control Center, where it carries different evidence.
     Storage can throw outright (private windows, blocked site data), so every
     read and write is guarded and the UI is correct with no stored value. */
  var page = (document.body.dataset.surface || location.pathname.split('/').pop() || 'app');

  function stored(name) {
    try { return localStorage.getItem('refinix.panel.' + page + '.' + name); }
    catch (_) { return null; }
  }
  function store(name, value) {
    try { localStorage.setItem('refinix.panel.' + page + '.' + name, value); }
    catch (_) { /* not worth telling anyone about */ }
  }

  var panels = {
    nav:  { el: document.querySelector('.nav'),  mq: NAV_OVERLAY,  toggle: null },
    rail: { el: document.querySelector('.rail'), mq: RAIL_OVERLAY, toggle: null }
  };

  function isOpen(name) { return app.dataset[name] === 'open'; }

  /* The scrim is driven entirely by CSS — `.app[data-nav="open"] ~ .panel-scrim`,
     declared inside the same media queries as the overlays. That keeps one
     source of truth: only an overlay raises a scrim, and a collapsed track on
     a wide window is just a narrower grid with nothing to dismiss. */
  function set(name, open, remember) {
    var panel = panels[name];
    if (!panel || !panel.el) return;
    app.dataset[name] = open ? 'open' : 'closed';
    if (panel.toggle) panel.toggle.setAttribute('aria-expanded', String(open));
    if (remember !== false) store(name, open ? 'open' : 'closed');
  }

  Array.prototype.forEach.call(
    document.querySelectorAll('[data-panel-toggle]'),
    function (btn) {
      var name = btn.getAttribute('data-panel-toggle');
      if (!panels[name] || !panels[name].el) { btn.hidden = true; return; }
      panels[name].toggle = btn;
      btn.addEventListener('click', function () { set(name, !isOpen(name)); });
    }
  );

  /* Initial state. A stored choice wins on a wide window; on a narrow one both
     walls start closed regardless, because opening over the conversation is
     never the right thing to do to someone who just loaded the page. */
  ['nav', 'rail'].forEach(function (name) {
    var panel = panels[name];
    if (!panel.el) return;
    var open = panel.mq.matches ? false : stored(name) !== 'closed';
    set(name, open, false);
  });

  /* Crossing a breakpoint changes what the same state means, so re-resolve it:
     leaving overlay mode restores the remembered choice, entering it closes. */
  ['nav', 'rail'].forEach(function (name) {
    var panel = panels[name];
    if (!panel.el || !panel.mq.addEventListener) return;
    panel.mq.addEventListener('change', function (e) {
      set(name, e.matches ? false : stored(name) !== 'closed', false);
    });
  });

  scrim.addEventListener('click', function () {
    ['nav', 'rail'].forEach(function (name) {
      if (panels[name].mq.matches && isOpen(name)) set(name, false);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    /* Escape closes an overlay and returns focus to the control that opened
       it. It deliberately does not collapse a docked panel on a wide window —
       that is a layout preference, not a thing you are trapped in. */
    ['nav', 'rail'].forEach(function (name) {
      if (panels[name].mq.matches && isOpen(name)) {
        set(name, false);
        if (panels[name].toggle) panels[name].toggle.focus();
      }
    });
  });
})();
