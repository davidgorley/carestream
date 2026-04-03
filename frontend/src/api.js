const API_BASE = window.location.origin + '/api';

async function fetchJSON(url, options = {}) {
  const res = await fetch(API_BASE + url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Request failed');
  }
  return res.json();
}

// Rooms
export const getRooms = () => fetchJSON('/rooms');
export const createRoom = (data) => fetchJSON('/rooms', { method: 'POST', body: JSON.stringify(data) });
export const updateRoom = (id, data) => fetchJSON(`/rooms/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteRoom = (id) => fetchJSON(`/rooms/${id}`, { method: 'DELETE' });
export const csvPreview = (file) => {
  const fd = new FormData();
  fd.append('file', file);
  return fetch(API_BASE + '/rooms/csv-preview', { method: 'POST', body: fd }).then(r => r.json());
};
export const csvImport = (rows) => fetchJSON('/rooms/csv-import', { method: 'POST', body: JSON.stringify({ rows }) });
export const csvTemplateUrl = API_BASE + '/rooms/csv-template';

// Media
export const getMedia = () => fetchJSON('/media');
export const getMediaStructure = () => fetchJSON('/media/structure');
export const getFolders = () => fetchJSON('/media/folders');
export const createFolder = (folderName) => fetchJSON('/media/folders', { method: 'POST', body: JSON.stringify({ folder_name: folderName }) });
export const deleteFolder = (folderId) => fetchJSON(`/media/folders/${folderId}`, { method: 'DELETE' });
export const uploadMedia = (file, folder, onProgress) => {
  return new Promise((resolve, reject) => {
    const fd = new FormData();
    fd.append('file', file);
    if (folder) fd.append('folder', folder);
    const xhr = new XMLHttpRequest();
    xhr.open('POST', API_BASE + '/media/upload');
    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round(e.loaded / e.total * 100));
      };
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText));
      else reject(new Error(JSON.parse(xhr.responseText).error || 'Upload failed'));
    };
    xhr.onerror = () => reject(new Error('Upload failed'));
    xhr.send(fd);
  });
};
export const renameMedia = (id, newFilename) => fetchJSON(`/media/${id}/rename`, { method: 'PUT', body: JSON.stringify({ filename: newFilename }) });
export const moveMedia = (id, folder) => fetchJSON(`/media/${id}/move`, { method: 'PUT', body: JSON.stringify({ folder }) });
export const deleteMedia = (id) => fetchJSON(`/media/${id}`, { method: 'DELETE' });

// Playlists
export const getPlaylists = () => fetchJSON('/playlists');
export const getPlaylist = (id) => fetchJSON(`/playlists/${id}`);
export const createPlaylist = (data) => fetchJSON('/playlists', { method: 'POST', body: JSON.stringify(data) });
export const updatePlaylist = (id, data) => fetchJSON(`/playlists/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deletePlaylist = (id) => fetchJSON(`/playlists/${id}`, { method: 'DELETE' });

// Push
export const pushContent = (data) => fetchJSON('/push', { method: 'POST', body: JSON.stringify(data) });
export const getPushLogs = (roomId) => fetchJSON(`/push/log${roomId ? '?room_id=' + roomId : ''}`);

// Settings
export const getSettings = () => fetchJSON('/settings');
export const updateSettings = (data) => fetchJSON('/settings', { method: 'PUT', body: JSON.stringify(data) });
export const getTimezone = () => fetchJSON('/settings/timezone');
export const setTimezone = (timezone) => fetchJSON('/settings/timezone', { method: 'POST', body: JSON.stringify({ timezone }) });
