import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getMedia, getFolders, uploadMedia, deleteMedia, renameMedia, moveMedia, createFolder, deleteFolder, getPlaylists, getPlaylist, createPlaylist, updatePlaylist, deletePlaylist, getTimezone } from '../api';

function MediaManager() {
  const [activeTab, setActiveTab] = useState('files');
  const [mediaFiles, setMediaFiles] = useState([]);
  const [folders, setFolders] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [timezone, setTimezone] = useState('America/New_York');
  const [dragOver, setDragOver] = useState(false);
  const [toasts, setToasts] = useState([]);
  const fileInputRef = useRef(null);

  // File explorer state
  const [currentPath, setCurrentPath] = useState('');  // e.g., "Training/Videos"
  const [selectedItems, setSelectedItems] = useState(new Set());  // Set of "file-{id}" or "folder-{name}"
  const [newFolderName, setNewFolderName] = useState('');
  const [renamingId, setRenamingId] = useState(null);
  const [renamingName, setRenamingName] = useState('');
  const [contextMenu, setContextMenu] = useState(null);  // { x, y, type, target }
  const [lastSelectedIdx, setLastSelectedIdx] = useState(null);  // For shift-click multi-select

  // Playlist state
  const [showPlaylistModal, setShowPlaylistModal] = useState(false);
  const [editingPlaylist, setEditingPlaylist] = useState(null);
  const [playlistName, setPlaylistName] = useState('');
  const [playlistItems, setPlaylistItems] = useState([]);
  const [draggedItem, setDraggedItem] = useState(null);

  const addToast = (message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 5000);
  };

  const loadMedia = useCallback(async () => {
    try { setMediaFiles(await getMedia()); } catch (e) { console.error(e); }
  }, []);

  const loadFolders = useCallback(async () => {
    try { setFolders(await getFolders()); } catch (e) { console.error(e); }
  }, []);

  const loadPlaylists = useCallback(async () => {
    try { setPlaylists(await getPlaylists()); } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { loadMedia(); loadFolders(); loadPlaylists(); getTimezone().then(data => setTimezone(data.timezone)).catch(e => console.error(e)); }, [loadMedia, loadFolders, loadPlaylists]);

  // Build hierarchical folder structure from flat folder list
  const buildFolderTree = () => {
    const tree = {};
    folders.forEach(f => {
      const parts = f.name.split('/').filter(p => p);
      let current = tree;
      parts.forEach((part, idx) => {
        if (!current[part]) {
          current[part] = { isFolder: true, children: {}, fullPath: parts.slice(0, idx + 1).join('/') };
        }
        current = current[part].children;
      });
    });
    return tree;
  };

  // Get items (folders and files) for current path
  const getItemsInPath = (path) => {
    const folderItems = [];
    const fileItems = [];

    // Get subfolders in current path
    const tree = buildFolderTree();
    let current = tree;
    if (path) {
      const parts = path.split('/').filter(p => p);
      for (const part of parts) {
        if (current[part]) current = current[part].children;
        else return { folders: [], files: [] };
      }
    }

    // Folders that are direct children of current path
    Object.entries(current).forEach(([name, node]) => {
      if (node.isFolder) {
        const fullPath = path ? `${path}/${name}` : name;
        const fileCount = mediaFiles.filter(f => f.folder.startsWith(fullPath + '/') || f.folder === fullPath).length;
        folderItems.push({
          name,
          fullPath,
          fileCount,
          type: 'folder'
        });
      }
    });

    // Files in current path (but not in subfolders)
    mediaFiles.forEach(f => {
      const fileFolder = f.folder || '';
      if (fileFolder === path) {
        fileItems.push({ ...f, type: 'file' });
      }
    });

    return { folders: folderItems, files: fileItems };
  };

  const { folders: currentFolders, files: currentFiles } = getItemsInPath(currentPath);

  // Navigation
  const navigateTo = (newPath) => {
    setCurrentPath(newPath);
    setSelectedItems(new Set());
  };

  const goBack = () => {
    const parts = currentPath.split('/').filter(p => p);
    if (parts.length > 0) {
      parts.pop();
      navigateTo(parts.join('/'));
    }
  };

  const getBreadcrumbs = () => {
    const crumbs = [];
    crumbs.push({ label: 'Root', path: '' });
    if (currentPath) {
      const parts = currentPath.split('/').filter(p => p);
      let accumulated = '';
      parts.forEach(part => {
        accumulated = accumulated ? `${accumulated}/${part}` : part;
        crumbs.push({ label: part, path: accumulated });
      });
    }
    return crumbs;
  };

  // Selection management
  const toggleSelection = (itemId, isMultiSelect = false, isShiftClick = false) => {
    const newSelected = new Set(selectedItems);

    if (isShiftClick && lastSelectedIdx !== null) {
      // Implement shift-click range selection
      const allItems = [...currentFolders, ...currentFiles];
      const currentIdx = allItems.findIndex(item => getItemId(item) === itemId);
      const start = Math.min(lastSelectedIdx, currentIdx);
      const end = Math.max(lastSelectedIdx, currentIdx);
      for (let i = start; i <= end; i++) {
        newSelected.add(getItemId(allItems[i]));
      }
      setLastSelectedIdx(currentIdx);
    } else if (isMultiSelect) {
      if (newSelected.has(itemId)) {
        newSelected.delete(itemId);
      } else {
        newSelected.add(itemId);
      }
      const allItems = [...currentFolders, ...currentFiles];
      const idx = allItems.findIndex(item => getItemId(item) === itemId);
      setLastSelectedIdx(idx);
    } else {
      newSelected.clear();
      newSelected.add(itemId);
      const allItems = [...currentFolders, ...currentFiles];
      const idx = allItems.findIndex(item => getItemId(item) === itemId);
      setLastSelectedIdx(idx);
    }

    setSelectedItems(newSelected);
  };

  const selectAll = () => {
    const all = new Set();
    [...currentFolders, ...currentFiles].forEach(item => all.add(getItemId(item)));
    setSelectedItems(all);
  };

  const getItemId = (item) => `${item.type}-${item.type === 'file' ? item.id : item.fullPath}`;

  const isSelected = (item) => selectedItems.has(getItemId(item));

  // File operations
  const handleUpload = async (files) => {
    for (const file of files) {
      if (!file.name.toLowerCase().endsWith('.mp4')) {
        addToast(file.name + ' is not an MP4 file', 'error');
        continue;
      }
      setUploading(true);
      setUploadProgress(0);
      try {
        await uploadMedia(file, currentPath, (p) => setUploadProgress(p));
        addToast(file.name + ' uploaded successfully', 'success');
        loadMedia();
      } catch (e) {
        addToast('Upload failed: ' + e.message, 'error');
      }
      setUploading(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    
    // Check if dropping on a folder (has dataset or target data)
    const dropZoneData = e.dataTransfer.getData('folderPath');
    if (dropZoneData) {
      // This is folder-to-folder, would need API support
      return;
    }

    if (e.dataTransfer.files.length > 0) handleUpload(Array.from(e.dataTransfer.files));
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.effectAllowed = 'copy';
  };

  const handleDropOnFolder = async (e, targetFolderPath) => {
    e.preventDefault();
    e.stopPropagation();
    
    // Get dragged item info from dataTransfer
    const draggedItemId = e.dataTransfer.getData('itemId');
    const draggedItemType = e.dataTransfer.getData('itemType');
    
    if (!draggedItemId) return;

    try {
      if (draggedItemType === 'file') {
        const fileId = parseInt(draggedItemId);
        await moveMedia(fileId, targetFolderPath);
        addToast('File moved successfully', 'success');
        loadMedia();
      }
      // TODO: Support folder-to-folder move
    } catch (e) {
      addToast('Move failed: ' + e.message, 'error');
    }
  };

  const handleDelete = async (id) => {
    const file = mediaFiles.find(f => f.id === id);
    if (!window.confirm(`Delete "${file.filename}"?`)) return;
    try {
      await deleteMedia(id);
      addToast(file.filename + ' deleted', 'success');
      loadMedia();
      setSelectedItems(prev => {
        const next = new Set(prev);
        next.delete(getItemId(file));
        return next;
      });
    } catch (e) { addToast('Delete failed: ' + e.message, 'error'); }
  };

  const handleDeleteFolder = async (folderPath) => {
    const fileCount = mediaFiles.filter(f => f.folder.startsWith(folderPath + '/') || f.folder === folderPath).length;
    if (fileCount > 0) {
      addToast('Cannot delete folder with files inside', 'error');
      return;
    }
    if (!window.confirm(`Delete folder "${folderPath.split('/').pop()}"?`)) return;
    try {
      const folderToDelete = folders.find(f => f.name === folderPath);
      if (folderToDelete) {
        await deleteFolder(folderToDelete.id);
        addToast('Folder deleted', 'success');
        loadFolders();
        setSelectedItems(prev => {
          const next = new Set(prev);
          next.delete(getItemId({ type: 'folder', fullPath: folderPath }));
          return next;
        });
      }
    } catch (e) { addToast('Delete failed: ' + e.message, 'error'); }
  };

  const handleRename = async (item) => {
    if (item.type === 'file') {
      setRenamingId(item.id);
      setRenamingName(item.filename.replace('.mp4', ''));
    }
  };

  const confirmRename = async (item) => {
    if (!renamingName.trim()) {
      addToast('Name cannot be empty', 'error');
      return;
    }
    try {
      await renameMedia(item.id, renamingName);
      addToast('File renamed successfully', 'success');
      loadMedia();
      setRenamingId(null);
    } catch (e) {
      addToast('Rename failed: ' + e.message, 'error');
    }
  };

  const handleCreateFolder = async () => {
    const folderName = newFolderName.trim();
    if (!folderName) {
      addToast('Folder name is required', 'error');
      return;
    }
    
    // Create full path for new folder
    const fullPath = currentPath ? `${currentPath}/${folderName}` : folderName;
    
    try {
      await createFolder(fullPath);
      addToast('Folder created', 'success');
      setNewFolderName('');
      loadFolders();
    } catch (e) {
      addToast('Failed to create folder: ' + e.message, 'error');
    }
  };

  const openPlaylistBuilder = (playlist = null) => {
    if (playlist) {
      setEditingPlaylist(playlist);
      setPlaylistName(playlist.name);
      getPlaylist(playlist.id).then(p => {
        setPlaylistItems(p.items ? p.items.map(i => i.media_file) : []);
      });
    } else {
      setEditingPlaylist(null);
      setPlaylistName('');
      setPlaylistItems([]);
    }
    setShowPlaylistModal(true);
  };

  const addToPlaylist = (file) => {
    if (!playlistItems.find(i => i.id === file.id)) {
      setPlaylistItems(prev => [...prev, file]);
    }
  };

  const removeFromPlaylist = (fileId) => {
    setPlaylistItems(prev => prev.filter(i => i.id !== fileId));
  };

  const handlePlaylistDragStart = (idx) => { setDraggedItem(idx); };
  const handlePlaylistDragOver = (e, idx) => {
    e.preventDefault();
    if (draggedItem === null || draggedItem === idx) return;
    const items = [...playlistItems];
    const dragged = items[draggedItem];
    items.splice(draggedItem, 1);
    items.splice(idx, 0, dragged);
    setDraggedItem(idx);
    setPlaylistItems(items);
  };
  const handlePlaylistDragEnd = () => { setDraggedItem(null); };

  const savePlaylist = async () => {
    if (!playlistName.trim()) { addToast('Playlist name is required', 'error'); return; }
    try {
      const data = { name: playlistName, media_ids: playlistItems.map(i => i.id) };
      if (editingPlaylist) {
        await updatePlaylist(editingPlaylist.id, data);
        addToast('Playlist "' + playlistName + '" updated', 'success');
      } else {
        await createPlaylist(data);
        addToast('Playlist "' + playlistName + '" created', 'success');
      }
      setShowPlaylistModal(false);
      loadPlaylists();
    } catch (e) { addToast(e.message, 'error'); }
  };

  const handleDeletePlaylist = async (id, name) => {
    if (!window.confirm('Delete playlist "' + name + '"?')) return;
    try {
      await deletePlaylist(id);
      addToast('Playlist "' + name + '" deleted', 'success');
      loadPlaylists();
    } catch (e) { addToast(e.message, 'error'); }
  };

  const formatDuration = (s) => {
    if (!s) return '0:00';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return m + ':' + sec.toString().padStart(2, '0');
  };

  const formatTime = (iso) => {
    if (!iso) return 'Never';
    const date = new Date(iso);
    return date.toLocaleDateString('en-US', { timeZone: timezone });
  };

  const formatSize = (b) => {
    if (!b) return '0 B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MB';
    return (b / 1073741824).toFixed(2) + ' GB';
  };

  // Context menu handling
  const handleContextMenu = (e, item) => {
    e.preventDefault();
    if (!isSelected(item)) toggleSelection(getItemId(item));
    setContextMenu({ x: e.clientX, y: e.clientY, type: item.type, target: item });
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (activeTab !== 'files') return;
      
      if (e.key === 'Delete') {
        selectedItems.forEach(itemId => {
          if (itemId.startsWith('file-')) {
            const fileId = parseInt(itemId.split('-')[1]);
            const file = mediaFiles.find(f => f.id === fileId);
            if (file) handleDelete(file.id);
          } else if (itemId.startsWith('folder-')) {
            const folderPath = itemId.substring(7);
            handleDeleteFolder(folderPath);
          }
        });
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        e.preventDefault();
        selectAll();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedItems, activeTab, mediaFiles]);

  return (
    <div>
      <div className="section-header">
        <h2><i className="fas fa-film" style={{ marginRight: 8, color: 'var(--primary)' }}></i>Media Manager</h2>
      </div>

      <div className="sub-tabs">
        <button className={'sub-tab ' + (activeTab === 'files' ? 'active' : '')} onClick={() => setActiveTab('files')}>
          <i className="fas fa-folder" style={{ marginRight: 6 }}></i>File Explorer
        </button>
        <button className={'sub-tab ' + (activeTab === 'playlists' ? 'active' : '')} onClick={() => setActiveTab('playlists')}>
          <i className="fas fa-list" style={{ marginRight: 6 }}></i>Playlists
        </button>
      </div>

      {activeTab === 'files' && (
        <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 200px)' }}>
          {/* Upload Area */}
          <div
            className={'drop-zone ' + (dragOver ? 'drag-over' : '')}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{ marginBottom: 20 }}
          >
            <i className="fas fa-cloud-upload-alt"></i>
            <p style={{ fontSize: 16, fontWeight: 500 }}>
              {uploading ? 'Uploading... ' + uploadProgress + '%' : 'Drag & drop MP4 files here or click to browse'}
            </p>
            {uploading && (
              <div className="progress-bar" style={{ maxWidth: 300, margin: '12px auto 0' }}>
                <div className="progress-bar-fill" style={{ width: uploadProgress + '%' }}></div>
              </div>
            )}
            <input ref={fileInputRef} type="file" accept=".mp4" multiple hidden
                   onChange={e => e.target.files.length && handleUpload(Array.from(e.target.files))} />
          </div>

          {/* Breadcrumb Navigation */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap', padding: '0 16px', backgroundColor: 'var(--bg-secondary)', borderRadius: 6, paddingTop: 12, paddingBottom: 12 }}>
            {getBreadcrumbs().map((crumb, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <button
                  className="btn btn-sm btn-outline"
                  onClick={() => navigateTo(crumb.path)}
                  style={{ padding: '4px 8px', fontSize: 12 }}
                >
                  {idx === 0 ? <i className="fas fa-home" style={{ marginRight: 4 }}></i> : null}
                  {crumb.label}
                </button>
                {idx < getBreadcrumbs().length - 1 && <span style={{ color: 'var(--text-secondary)' }}>/</span>}
              </div>
            ))}
            {currentPath && (
              <button
                className="btn btn-sm btn-outline"
                onClick={goBack}
                style={{ marginLeft: 'auto', padding: '4px 8px', fontSize: 12 }}
              >
                <i className="fas fa-arrow-left" style={{ marginRight: 4 }}></i>
                Back
              </button>
            )}
          </div>

          {/* Toolbar */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16, alignItems: 'flex-end' }}>
            <input
              className="input"
              value={newFolderName}
              onChange={e => setNewFolderName(e.target.value)}
              onKeyPress={e => e.key === 'Enter' && handleCreateFolder()}
              placeholder="New folder name..."
              style={{ flex: 1, maxWidth: 300 }}
            />
            <button
              className="btn btn-primary"
              onClick={handleCreateFolder}
              title="Create new folder (Ctrl+Shift+N)"
            >
              <i className="fas fa-folder-plus" style={{ marginRight: 6 }}></i>
              New Folder
            </button>
            {selectedItems.size > 0 && (
              <>
                <span style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                  {selectedItems.size} selected
                </span>
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => {
                    if (window.confirm(`Delete ${selectedItems.size} item(s)?`)) {
                      selectedItems.forEach(itemId => {
                        if (itemId.startsWith('file-')) {
                          const fileId = parseInt(itemId.split('-')[1]);
                          handleDelete(fileId);
                        } else if (itemId.startsWith('folder-')) {
                          const folderPath = itemId.substring(7);
                          handleDeleteFolder(folderPath);
                        }
                      });
                    }
                  }}
                  style={{ padding: '6px 12px' }}
                >
                  <i className="fas fa-trash" style={{ marginRight: 4 }}></i>
                  Delete
                </button>
              </>
            )}
          </div>

          {/* File Explorer Grid */}
          <div
            className="card"
            style={{
              flex: 1,
              overflow: 'auto',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))',
              gap: 12,
              padding: 16,
              alignContent: 'start'
            }}
            onContextMenu={e => { e.preventDefault(); setContextMenu(null); }}
            onClick={() => setContextMenu(null)}
            onKeyDown={e => {
              if (e.ctrlKey && e.key === 'a') {
                e.preventDefault();
                selectAll();
              }
            }}
          >
            {currentFolders.length === 0 && currentFiles.length === 0 ? (
              <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>
                <i className="fas fa-inbox" style={{ fontSize: 48, marginBottom: 16, opacity: 0.5 }}></i>
                <p>This folder is empty</p>
              </div>
            ) : (
              <>
                {/* Folders */}
                {currentFolders.map(folder => {
                  const itemId = getItemId(folder);
                  const selected = isSelected(folder);
                  return (
                    <div
                      key={folder.fullPath}
                      onClick={(e) => {
                        if (e.detail === 2) { // Double-click
                          navigateTo(folder.fullPath);
                        } else if (e.detail === 1) { // Single-click
                          toggleSelection(itemId, e.ctrlKey || e.metaKey, e.shiftKey);
                        }
                      }}
                      onContextMenu={(e) => handleContextMenu(e, folder)}
                      onDragOver={(e) => {
                        e.preventDefault();
                        e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.2)';
                        e.currentTarget.style.borderColor = 'var(--primary)';
                      }}
                      onDragLeave={(e) => {
                        e.currentTarget.style.backgroundColor = selected ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-secondary)';
                        e.currentTarget.style.borderColor = selected ? 'var(--primary)' : 'var(--border)';
                      }}
                      onDrop={(e) => handleDropOnFolder(e, folder.fullPath)}
                      style={{
                        padding: 12,
                        border: selected ? '2px solid var(--primary)' : '2px solid var(--border)',
                        borderRadius: 8,
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        backgroundColor: selected ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-secondary)',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        textAlign: 'center'
                      }}
                      onMouseEnter={e => !selected && (e.currentTarget.style.backgroundColor = '#e8f0ff')}
                      onMouseLeave={e => !selected && (e.currentTarget.style.backgroundColor = 'var(--bg-secondary)')}
                    >
                      <div style={{ fontSize: 36, marginBottom: 8, color: 'var(--primary)' }}>
                        <i className="fas fa-folder"></i>
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 500, marginBottom: 4, wordBreak: 'break-word', maxHeight: 40, overflow: 'hidden' }}>
                        {folder.name}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                        {folder.fileCount} file{folder.fileCount !== 1 ? 's' : ''}
                      </div>
                    </div>
                  );
                })}

                {/* Files */}
                {currentFiles.map(file => {
                  const itemId = getItemId(file);
                  const selected = isSelected(file);
                  return (
                    <div
                      key={file.id}
                      draggable
                      onDragStart={(e) => {
                        e.dataTransfer.effectAllowed = 'move';
                        e.dataTransfer.setData('itemId', file.id.toString());
                        e.dataTransfer.setData('itemType', 'file');
                      }}
                      onDragEnd={(e) => {
                        e.dataTransfer.dropEffect = 'move';
                      }}
                      onClick={(e) => {
                        toggleSelection(itemId, e.ctrlKey || e.metaKey, e.shiftKey);
                      }}
                      onContextMenu={(e) => handleContextMenu(e, file)}
                      onDoubleClick={() => handleRename(file)}
                      style={{
                        padding: 12,
                        border: selected ? '2px solid var(--primary)' : '2px solid var(--border)',
                        borderRadius: 8,
                        cursor: 'move',
                        transition: 'all 0.2s',
                        backgroundColor: selected ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-secondary)',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        textAlign: 'center'
                      }}
                      onMouseEnter={e => !selected && (e.currentTarget.style.backgroundColor = '#e8f0ff')}
                      onMouseLeave={e => !selected && (e.currentTarget.style.backgroundColor = 'var(--bg-secondary)')}
                    >
                      {renamingId === file.id ? (
                        <div style={{ width: '100%', marginBottom: 8 }}>
                          <input
                            className="input"
                            value={renamingName}
                            onChange={e => setRenamingName(e.target.value)}
                            onKeyDown={e => {
                              if (e.key === 'Enter') confirmRename(file);
                              if (e.key === 'Escape') setRenamingId(null);
                            }}
                            style={{ fontSize: 11 }}
                            autoFocus
                          />
                        </div>
                      ) : (
                        <>
                          <div style={{ fontSize: 32, marginBottom: 8, color: 'var(--primary)' }}>
                            <i className="fas fa-file-video"></i>
                          </div>
                          <div style={{ fontSize: 11, fontWeight: 500, marginBottom: 4, wordBreak: 'break-word', maxHeight: 40, overflow: 'hidden', minHeight: 22 }}>
                            {file.filename}
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 4 }}>
                            {formatSize(file.filesize)}
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                            {formatDuration(file.duration)}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </>
            )}
          </div>

          {/* Context Menu */}
          {contextMenu && (
            <div
              style={{
                position: 'fixed',
                top: contextMenu.y,
                left: contextMenu.x,
                backgroundColor: 'white',
                border: '1px solid var(--border)',
                borderRadius: 6,
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                zIndex: 10000,
                minWidth: 160
              }}
              onContextMenu={e => e.preventDefault()}
            >
              {contextMenu.type === 'file' && (
                <>
                  <button
                    onClick={() => { handleRename(contextMenu.target); setContextMenu(null); }}
                    style={{ display: 'block', width: '100%', padding: '8px 16px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left' }}
                    onMouseOver={e => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                    onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <i className="fas fa-pen" style={{ marginRight: 6, width: 16 }}></i>
                    Rename
                  </button>
                  <button
                    onClick={() => { handleDelete(contextMenu.target.id); setContextMenu(null); }}
                    style={{ display: 'block', width: '100%', padding: '8px 16px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', color: '#ef4444' }}
                    onMouseOver={e => e.currentTarget.style.backgroundColor = '#ffe5e5'}
                    onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <i className="fas fa-trash" style={{ marginRight: 6, width: 16 }}></i>
                    Delete
                  </button>
                  <button
                    onClick={() => { addToPlaylist(contextMenu.target); setContextMenu(null); addToast('Added to current playlist'); }}
                    style={{ display: 'block', width: '100%', padding: '8px 16px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left' }}
                    onMouseOver={e => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                    onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <i className="fas fa-list" style={{ marginRight: 6, width: 16 }}></i>
                    Add to Playlist
                  </button>
                </>
              )}
              {contextMenu.type === 'folder' && (
                <>
                  <button
                    onClick={() => { navigateTo(contextMenu.target.fullPath); setContextMenu(null); }}
                    style={{ display: 'block', width: '100%', padding: '8px 16px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left' }}
                    onMouseOver={e => e.currentTarget.style.backgroundColor = '#f5f5f5'}
                    onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <i className="fas fa-folder-open" style={{ marginRight: 6, width: 16 }}></i>
                    Open
                  </button>
                  <button
                    onClick={() => { handleDeleteFolder(contextMenu.target.fullPath); setContextMenu(null); }}
                    style={{ display: 'block', width: '100%', padding: '8px 16px', border: 'none', background: 'none', cursor: 'pointer', fontSize: 13, textAlign: 'left', color: '#ef4444' }}
                    onMouseOver={e => e.currentTarget.style.backgroundColor = '#ffe5e5'}
                    onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
                  >
                    <i className="fas fa-trash" style={{ marginRight: 6, width: 16 }}></i>
                    Delete
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'playlists' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <button className="btn btn-primary" onClick={() => openPlaylistBuilder()}>
              <i className="fas fa-plus"></i> Create Playlist
            </button>
          </div>

          {playlists.length === 0 ? (
            <div className="empty-state card">
              <i className="fas fa-list"></i>
              <p>No playlists created yet</p>
            </div>
          ) : (
            <div className="card">
              <div className="table-container">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Files</th>
                      <th>Total Duration</th>
                      <th>Created</th>
                      <th style={{ width: 120 }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {playlists.map(p => (
                      <tr key={p.id}>
                        <td><i className="fas fa-list" style={{ marginRight: 8, color: 'var(--primary)' }}></i>{p.name}</td>
                        <td>{p.item_count}</td>
                        <td>{formatDuration(p.total_duration)}</td>
                        <td>{new Date(p.created_at).toLocaleDateString('en-US', { timeZone: timezone })}</td>
                        <td>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button className="btn btn-secondary btn-sm" onClick={() => openPlaylistBuilder(p)}>
                              <i className="fas fa-edit"></i>
                            </button>
                            <button className="btn btn-danger btn-sm" onClick={() => handleDeletePlaylist(p.id, p.name)}>
                              <i className="fas fa-trash"></i>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {showPlaylistModal && (
        <div className="modal-overlay" onClick={() => setShowPlaylistModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 700 }}>
            <div className="modal-header">
              <h3>{editingPlaylist ? 'Edit Playlist' : 'Create Playlist'}</h3>
              <button className="modal-close" onClick={() => setShowPlaylistModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Playlist Name</label>
                <input className="input" value={playlistName} onChange={e => setPlaylistName(e.target.value)} placeholder="e.g., Morning Relaxation" />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
                <div>
                  <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Available Files</h4>
                  <div style={{ maxHeight: 300, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 6 }}>
                    {mediaFiles.length === 0 ? (
                      <p style={{ padding: 16, fontSize: 13, color: 'var(--text-secondary)' }}>No files uploaded</p>
                    ) : mediaFiles.map(f => (
                      <div key={f.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', borderBottom: '1px solid #f1f5f9' }}>
                        <div style={{ fontSize: 13 }}>
                          <div>{f.filename}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{formatDuration(f.duration)}</div>
                        </div>
                        <button className="btn btn-sm btn-outline" onClick={() => addToPlaylist(f)}
                          disabled={playlistItems.find(i => i.id === f.id)}>
                          <i className="fas fa-plus"></i>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <h4 style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Playlist Order ({playlistItems.length} files)</h4>
                  <div style={{ minHeight: 100, maxHeight: 300, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 6, padding: 8 }}>
                    {playlistItems.length === 0 ? (
                      <p style={{ padding: 16, fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center' }}>Add files from the left panel</p>
                    ) : playlistItems.map((item, idx) => (
                      <div
                        key={item.id + '-' + idx}
                        className="playlist-item"
                        draggable
                        onDragStart={() => handlePlaylistDragStart(idx)}
                        onDragOver={(e) => handlePlaylistDragOver(e, idx)}
                        onDragEnd={handlePlaylistDragEnd}
                        style={{ opacity: draggedItem === idx ? 0.5 : 1 }}
                      >
                        <span className="drag-handle"><i className="fas fa-grip-vertical"></i></span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', minWidth: 20 }}>{idx + 1}</span>
                        <span className="item-name">{item.filename}</span>
                        <span className="item-duration">{formatDuration(item.duration)}</span>
                        <button className="btn btn-sm btn-danger" style={{ padding: '2px 6px' }}
                          onClick={() => removeFromPlaylist(item.id)}>
                          <i className="fas fa-times"></i>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowPlaylistModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={savePlaylist} disabled={!playlistName.trim() || !playlistItems.length}>
                <i className="fas fa-save"></i> {editingPlaylist ? 'Update' : 'Create'} Playlist
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={'toast toast-' + t.type}>
            <i className={'fas ' + (t.type === 'success' ? 'fa-check-circle' : t.type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle')}></i>
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );
}

export default MediaManager;
