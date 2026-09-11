// ABOUTME: Shared board mechanics for arranging clothing cutouts on the
// ABOUTME: fixed 600x620 board — drag to move, corner handle to resize,
// ABOUTME: right-click to reorder/remove. Used by the outfit builder and
// ABOUTME: the calendar day board; each page wires its own save button.
function createBoardEditor(initialPieces) {
  var BOARD_W = 600, BOARD_H = 620;
  var board = document.getElementById('board');
  var boardEmpty = document.getElementById('board-empty');
  var ctxMenu = document.getElementById('ctx-menu');
  var trayGrid = document.getElementById('traygrid');
  var trayFilters = document.getElementById('tray-filters');
  var uidCounter = 0;

  var items = (initialPieces || []).map(function (p) {
    return { uid: 'u' + (uidCounter++), id: p.item_id, src: p.src, alt: p.alt, x: p.x, y: p.y, w: p.w, rot: p.rot };
  });

  var dragging = null;   // uid currently being repositioned
  var resizing = null;   // uid currently being resized
  var selectedUid = null;
  var moved = false;

  function clampW(w) { return Math.max(60, Math.min(500, w)); }

  function findItem(uid) { return items.find(function (x) { return x.uid === uid; }); }

  function bringToFront(uid) {
    var idx = items.findIndex(function (x) { return x.uid === uid; });
    if (idx === -1 || idx === items.length - 1) return;
    items.push(items.splice(idx, 1)[0]);
  }
  function sendToBack(uid) {
    var idx = items.findIndex(function (x) { return x.uid === uid; });
    if (idx <= 0) return;
    items.unshift(items.splice(idx, 1)[0]);
  }
  function removeItem(uid) {
    items = items.filter(function (x) { return x.uid !== uid; });
    if (selectedUid === uid) selectedUid = null;
    render();
  }

  function render() {
    board.querySelectorAll('.cutout').forEach(function (el) { el.remove(); });
    boardEmpty.style.display = items.length ? 'none' : 'flex';
    items.forEach(function (it, idx) {
      var div = document.createElement('div');
      div.className = 'cutout' + (it.uid === selectedUid ? ' selected' : '');
      div.style.left = it.x + 'px';
      div.style.top = it.y + 'px';
      div.style.width = it.w + 'px';
      div.style.transform = 'rotate(' + it.rot + 'deg)';
      div.style.zIndex = idx + 1;
      div.dataset.uid = it.uid;

      var img = document.createElement('img');
      img.src = it.src;
      img.alt = it.alt;
      img.draggable = false;
      div.appendChild(img);

      var rm = document.createElement('div');
      rm.className = 'remove';
      rm.textContent = '×';
      rm.addEventListener('mousedown', function (e) { e.stopPropagation(); });
      rm.addEventListener('click', function (e) {
        e.stopPropagation();
        removeItem(it.uid);
      });
      div.appendChild(rm);

      if (it.uid === selectedUid) {
        var handle = document.createElement('div');
        handle.className = 'resizehandle';
        handle.title = 'drag to resize';
        handle.addEventListener('mousedown', function (e) {
          e.stopPropagation();
          e.preventDefault();
          resizing = it.uid;
        });
        div.appendChild(handle);
      }

      div.addEventListener('mousedown', function (e) {
        if (e.button !== 0) return;
        e.preventDefault();
        moved = false;
        dragging = it.uid;
        bringToFront(it.uid); // dragging something always brings it to the top
        render();
      });

      div.addEventListener('contextmenu', function (e) {
        e.preventDefault();
        selectedUid = it.uid;
        ctxMenu.dataset.uid = it.uid;
        ctxMenu.style.left = e.clientX + 'px';
        ctxMenu.style.top = e.clientY + 'px';
        ctxMenu.hidden = false;
        render();
      });

      board.appendChild(div);
    });
  }
  render();

  document.addEventListener('mousemove', function (e) {
    if (dragging) {
      var it = findItem(dragging);
      if (it) {
        it.x += e.movementX;
        it.y += e.movementY;
        moved = true;
        var el = board.querySelector('.cutout[data-uid="' + dragging + '"]');
        if (el) { el.style.left = it.x + 'px'; el.style.top = it.y + 'px'; }
      }
    } else if (resizing) {
      var it2 = findItem(resizing);
      if (it2) {
        it2.w = clampW(it2.w + e.movementX);
        moved = true;
        var el2 = board.querySelector('.cutout[data-uid="' + resizing + '"]');
        if (el2) { el2.style.width = it2.w + 'px'; }
      }
    }
  });

  function stopDrag() {
    if (dragging) {
      var uid = dragging;
      dragging = null;
      selectedUid = moved ? uid : (selectedUid === uid ? null : uid);
      render();
    }
    if (resizing) {
      resizing = null;
      render();
    }
  }
  document.addEventListener('mouseup', stopDrag);

  board.addEventListener('mousedown', function (e) {
    if (e.target === board || e.target === boardEmpty) {
      selectedUid = null;
      ctxMenu.hidden = true;
      render();
    }
  });

  ctxMenu.addEventListener('click', function (e) {
    var actionEl = e.target.closest('[data-action]');
    if (!actionEl) return;
    var uid = ctxMenu.dataset.uid;
    if (actionEl.dataset.action === 'front') bringToFront(uid);
    else if (actionEl.dataset.action === 'back') sendToBack(uid);
    else if (actionEl.dataset.action === 'remove') removeItem(uid);
    ctxMenu.hidden = true;
    render();
  });
  document.addEventListener('click', function (e) {
    if (!ctxMenu.hidden && !ctxMenu.contains(e.target)) ctxMenu.hidden = true;
  });
  document.addEventListener('contextmenu', function (e) {
    if (!e.target.closest('.cutout')) ctxMenu.hidden = true;
  });

  function addItemFromTray(trayEl, dropPoint) {
    var w = 220;
    var x, y;
    if (dropPoint) {
      x = Math.round(dropPoint.x - w / 2);
      y = Math.round(dropPoint.y - w / 2);
    } else {
      var n = items.length;
      x = 60 + (n * 40) % (BOARD_W - w - 40);
      y = 40 + (n * 55) % (BOARD_H - 160);
    }
    var it = {
      uid: 'u' + (uidCounter++),
      id: trayEl.dataset.id,
      src: trayEl.dataset.src,
      alt: trayEl.dataset.alt,
      x: x, y: y, w: w,
      rot: Math.round((Math.random() * 14 - 7) * 10) / 10
    };
    items.push(it);
    selectedUid = it.uid;
    render();
  }

  if (trayGrid) {
    trayGrid.addEventListener('click', function (e) {
      var el = e.target.closest('.trayitem');
      if (!el) return;
      addItemFromTray(el, null);
    });
    trayGrid.querySelectorAll('.trayitem').forEach(function (el) {
      el.addEventListener('dragstart', function (e) {
        e.dataTransfer.setData('text/plain', el.dataset.id);
        e.dataTransfer.effectAllowed = 'copy';
      });
    });
  }
  board.addEventListener('dragover', function (e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  });
  board.addEventListener('drop', function (e) {
    e.preventDefault();
    var id = e.dataTransfer.getData('text/plain');
    if (!id || !trayGrid) return;
    var trayEl = trayGrid.querySelector('.trayitem[data-id="' + id + '"]');
    if (!trayEl) return;
    var rect = board.getBoundingClientRect();
    addItemFromTray(trayEl, { x: e.clientX - rect.left, y: e.clientY - rect.top });
  });

  if (trayFilters) {
    trayFilters.addEventListener('click', function (e) {
      var chip = e.target.closest('.chip');
      if (!chip) return;
      trayFilters.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('selected'); });
      chip.classList.add('selected');
      var type = chip.dataset.type;
      trayGrid.querySelectorAll('.trayitem').forEach(function (t) {
        t.style.display = (!type || t.dataset.type === type) ? 'flex' : 'none';
      });
    });
  }

  return {
    isEmpty: function () { return items.length === 0; },
    getPieces: function () {
      return items.map(function (it) {
        return { id: it.id, x: Math.round(it.x), y: Math.round(it.y), w: Math.round(it.w), rot: it.rot };
      });
    },
  };
}
