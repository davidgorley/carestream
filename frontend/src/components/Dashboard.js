import React, { useState, useEffect, useCallback } from 'react';
import { getRooms, getMedia, getPlaylists, pushContent, getPushLogs } from '../api';
import socket from '../socket';

function Dashboard() {
  const [rooms, setRooms] = useState([]);
  const [search, setSearch] = useState('');
  const [filterUnit, setFilterUnit] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [sortBy, setSortBy] = useState('room_number');
  const [sortDir, setSortDir] = useState('asc');
  const [selectedRoom, setSelectedRoom] = useState(null);
  const [media, setMedia] = useState([]);
  const [playlists, setPlaylists] = useState([]);
  const [selectedMedia, setSelectedMedia] = useState([]);
  const [selectedPlaylists, setSelectedPlaylists] = useState([]);
  const [pushProgress, setPushProgress] = useState({});
  const [toasts, setToasts] = useState([]);
  const [pushing, setPushing] = useState(false);
  const [modalTab, setModalTab] = useState('push');
  const [pushHistory, setPushHistory] = useState([]);

  const loadRooms = useCallback(async () => {
    try { const data = await getRooms(); setRooms(data); } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    loadRooms();
    const interval = setInterval(loadRooms, 30000);
    return () => clearInterval(interval);
  }, [loadRooms]);

  useEffect(() => {
    socket.on('room_update', (room) => {
      setRooms(prev => prev.map(r => r.id === room.id ? room : r));
    });
    socket.on('heartbeat_update', (data) => {
      if (data.rooms) setRooms(data.rooms);
    });
    socket.on('push_progress', (data) => {
      // Handle both progress updates and error status
      if (data.status === 'error') {
        addToast(`Push failed for room ${data.room_id}: ${data.message}`, 'error');
      }
      setPushProgress(prev => ({ ...prev, [data.room_id]: data }));
    });
    return () => {
      socket.off('room_update');
      socket.off('heartbeat_update');
      socket.off('push_progress');
    };
  }, []);

  const addToast = (message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 5000);
  };

  const openAssignment = async (room) => {
    setSelectedRoom(room);
    setSelectedMedia([]);
    setSelectedPlaylists([]);
    setModalTab('push');
    try {
      const [m, p, h] = await Promise.all([getMedia(), getPlaylists(), getPushLogs(room.id)]);
      setMedia(m);
      setPlaylists(p);
      setPushHistory(h);
    } catch (e) { console.error(e); }
  };

  const handlePush = async () => {
    if (!selectedRoom || (!selectedMedia.length && !selectedPlaylists.length)) return;
    setPushing(true);
    try {
      await pushContent({
        room_id: selectedRoom.id,
        media_ids: selectedMedia,
        playlist_ids: selectedPlaylists,
      });
      addToast(`Push initiated for ${selectedRoom.room_number}`, 'success');
      setSelectedRoom(null);
      loadRooms();
    } catch (e) {
      addToast(`Push failed: ${e.message}`, 'error');
    }
    setPushing(false);
  };

  const units = [...new Set(rooms.map(r => r.unit).filter(Boolean))];

  const filtered = rooms
    .filter(r => {
      if (search) {
        const s = search.toLowerCase();
        if (!r.room_number.toLowerCase().includes(s) &&
            !r.unit.toLowerCase().includes(s) &&
            !r.ip_address.includes(s)) return false;
      }
      if (filterUnit && r.unit !== filterUnit) return false;
      if (filterStatus && r.status !== filterStatus) return false;
      return true;
    })
    .sort((a, b) => {
      let va = a[sortBy] || '', vb = b[sortBy] || '';
      if (sortBy === 'last_push_time') {
        va = va || ''; vb = vb || '';
      }
      // For room_number, always use numeric comparison
      if (sortBy === 'room_number') {
        const numA = parseInt(va) || 0;
        const numB = parseInt(vb) || 0;
        const cmp = numA - numB;
        return sortDir === 'asc' ? cmp : -cmp;
      }
      const cmp = typeof va === 'string' ? va.localeCompare(vb) : va - vb;
      return sortDir === 'asc' ? cmp : -cmp;
    });

  const formatDuration = (s) => {
    if (!s) return '0:00';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  const formatSize = (b) => {
    if (!b) return '0 B';
    if (b < 1024) return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MB';
    return (b / 1073741824).toFixed(2) + ' GB';
  };

  const formatTime = (iso) => {
    if (!iso) return 'Never';
    const date = new Date(iso);
    return date.toLocaleString('en-US', { timeZone: 'America/Chicago' });
  };

  return (
    <div>
      <div className="section-header">
        <h2><i className="fas fa-th-large" style={{ marginRight: 8, color: 'var(--primary)' }}></i>Room Dashboard</h2>
        <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
          {rooms.length} rooms · {rooms.filter(r => r.status === 'online').length} online
        </span>
      </div>

      <div className="filter-bar">
        <input
          className="input"
          placeholder="Search rooms, units, IPs..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select value={filterUnit} onChange={e => setFilterUnit(e.target.value)}>
          <option value="">All Units</option>
          {units.map(u => <option key={u} value={u}>{u}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
          <option value="">All Status</option>
          <option value="online">Online</option>
          <option value="offline">Offline</option>
          <option value="unknown">Unknown</option>
        </select>
        <select value={`${sortBy}_${sortDir}`} onChange={e => {
          const [field, dir] = e.target.value.split('_');
          setSortBy(field); setSortDir(dir);
        }}>
          <option value="room_number_asc">Room # ↑</option>
          <option value="room_number_desc">Room # ↓</option>
          <option value="unit_asc">Unit A-Z</option>
          <option value="unit_desc">Unit Z-A</option>
          <option value="last_push_time_desc">Last Push ↓</option>
          <option value="status_asc">Status</option>
        </select>
      </div>

      {filtered.length === 0 ? (
        <div className="empty-state">
          <i className="fas fa-door-open"></i>
          <p>No rooms found. Add rooms in the Settings tab.</p>
        </div>
      ) : (
        <div className="room-grid">
          {filtered.map(room => {
            const prog = pushProgress[room.id];
            return (
              <div key={room.id} className="card" style={{ cursor: 'pointer', transition: 'transform 0.15s' }}
                   onClick={() => openAssignment(room)}
                   onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
                   onMouseLeave={e => e.currentTarget.style.transform = ''}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>{room.room_number}</div>
                    <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{room.unit}</div>
                  </div>
                  <span className={`badge badge-${room.status || 'unknown'}`}>
                    <i className={`fas fa-circle`} style={{ fontSize: 6 }}></i>
                    {room.status || 'unknown'}
                  </span>
                </div>

                <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
                  <i className="fas fa-network-wired" style={{ marginRight: 6 }}></i>
                  {room.ip_address}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span className={`badge badge-${room.push_status || 'idle'}`}>
                    {room.push_status || 'idle'}
                  </span>
                  {room.last_checked && (
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                      Checked: {formatTime(room.last_checked)}
                    </span>
                  )}
                </div>

                {room.last_push_file && (
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>
                    <i className="fas fa-file-video" style={{ marginRight: 4 }}></i>
                    {room.last_push_file}
                    {room.last_push_time && <span> · {formatTime(room.last_push_time)}</span>}
                  </div>
                )}

                {prog && (room.push_status === 'pushing' || prog.status === 'pushing' || prog.status === 'playing') && (
                  <div style={{ marginTop: 8 }}>
                    <div style={{ fontSize: 12, color: 'var(--primary)', marginBottom: 4 }}>{prog.message}</div>
                    <div className="progress-bar">
                      <div className="progress-bar-fill" style={{ width: `${prog.overall_progress || prog.progress || 0}%` }}></div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Assignment Modal */}
      {selectedRoom && (
        <div className="modal-overlay" onClick={() => !pushing && setSelectedRoom(null)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 650 }}>
            <div className="modal-header">
              <h3>
                <i className="fas fa-paper-plane" style={{ marginRight: 8, color: 'var(--primary)' }}></i>
                {selectedRoom.room_number}
              </h3>
              <button className="modal-close" onClick={() => !pushing && setSelectedRoom(null)}>×</button>
            </div>
            
            {/* Modal Tabs */}
            <div className="sub-tabs" style={{ borderBottom: '1px solid var(--border)' }}>
              <button className={`sub-tab ${modalTab === 'push' ? 'active' : ''}`} onClick={() => setModalTab('push')}>
                <i className="fas fa-paper-plane" style={{ marginRight: 6 }}></i>Push Media
              </button>
              <button className={`sub-tab ${modalTab === 'history' ? 'active' : ''}`} onClick={() => setModalTab('history')}>
                <i className="fas fa-history" style={{ marginRight: 6 }}></i>History
              </button>
            </div>

            <div className="modal-body">
              <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
                <div className={`badge badge-${selectedRoom.status}`}>
                  <i className="fas fa-circle" style={{ fontSize: 6 }}></i>{selectedRoom.status}
                </div>
                <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                  {selectedRoom.unit} · {selectedRoom.ip_address}
                </span>
              </div>

              {modalTab === 'push' && (
                <>
                  {/* Push progress in modal */}
                  {pushProgress[selectedRoom.id] && selectedRoom.push_status === 'pushing' && (
                    <div className="card" style={{ marginBottom: 16, background: '#f0f5ff', border: '1px solid #bfdbfe' }}>
                      <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--primary)' }}>
                        {pushProgress[selectedRoom.id].message}
                      </div>
                      <div className="progress-bar" style={{ marginTop: 8 }}>
                        <div className="progress-bar-fill" style={{ width: `${pushProgress[selectedRoom.id].overall_progress || 0}%` }}></div>
                      </div>
                    </div>
                  )}

                  <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>
                    <i className="fas fa-file-video" style={{ marginRight: 6 }}></i>Media Files
                  </h4>
                  {media.length === 0 ? (
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>No media files uploaded yet.</p>
                  ) : (
                    <div style={{ maxHeight: 200, overflowY: 'auto', marginBottom: 16, border: '1px solid var(--border)', borderRadius: 6 }}>
                      {media.map(m => (
                        <div key={m.id} className="checkbox-item" style={{ padding: '8px 12px' }}>
                          <input type="checkbox" id={`media-${m.id}`}
                            checked={selectedMedia.includes(m.id)}
                            onChange={e => {
                              if (e.target.checked) setSelectedMedia(prev => [...prev, m.id]);
                              else setSelectedMedia(prev => prev.filter(id => id !== m.id));
                            }} />
                          <label htmlFor={`media-${m.id}`} style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                            <span>{m.filename}</span>
                            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                              {formatSize(m.filesize)} · {formatDuration(m.duration)}
                            </span>
                          </label>
                        </div>
                      ))}
                    </div>
                  )}

                  <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>
                    <i className="fas fa-list" style={{ marginRight: 6 }}></i>Playlists
                  </h4>
                  {playlists.length === 0 ? (
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>No playlists created yet.</p>
                  ) : (
                    <div style={{ maxHeight: 200, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 6 }}>
                      {playlists.map(p => (
                        <div key={p.id} className="checkbox-item" style={{ padding: '8px 12px' }}>
                          <input type="checkbox" id={`pl-${p.id}`}
                            checked={selectedPlaylists.includes(p.id)}
                            onChange={e => {
                              if (e.target.checked) setSelectedPlaylists(prev => [...prev, p.id]);
                              else setSelectedPlaylists(prev => prev.filter(id => id !== p.id));
                            }} />
                          <label htmlFor={`pl-${p.id}`} style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                            <span>{p.name}</span>
                            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                              {p.item_count} files · {formatDuration(p.total_duration)}
                            </span>
                          </label>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {modalTab === 'history' && (
                <>
                  <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>
                    <i className="fas fa-history" style={{ marginRight: 6 }}></i>Push History
                  </h4>
                  {pushHistory.length === 0 ? (
                    <div className="empty-state" style={{ padding: 30 }}>
                      <i className="fas fa-inbox"></i>
                      <p>No push history yet</p>
                    </div>
                  ) : (
                    <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                      {pushHistory.map(log => (
                        <div key={log.id} className="card" style={{ marginBottom: 10, padding: 12 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
                            <div>
                              <div style={{ fontSize: 13, fontWeight: 500 }}>{log.media_ref}</div>
                              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                                {formatTime(log.started_at)}
                              </div>
                            </div>
                            <div className={`badge badge-${log.status}`}>
                              {log.status === 'success' && <i className="fas fa-check-circle"></i>}
                              {log.status === 'error' && <i className="fas fa-exclamation-circle"></i>}
                              {log.status === 'pending' && <i className="fas fa-clock"></i>}
                              {' '}
                              {log.status}
                            </div>
                          </div>
                          {log.completed_at && (
                            <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                              Completed: {formatTime(log.completed_at)}
                            </div>
                          )}
                          {log.error_message && (
                            <div style={{ fontSize: 11, color: '#ef4444', marginTop: 4 }}>
                              <strong>Error:</strong> {log.error_message}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setSelectedRoom(null)} disabled={pushing}>Cancel</button>
              {modalTab === 'push' && (
                <button className="btn btn-primary" onClick={handlePush}
                  disabled={pushing || (!selectedMedia.length && !selectedPlaylists.length)}>
                  {pushing ? <><i className="fas fa-spinner fa-spin"></i> Pushing...</> : <><i className="fas fa-paper-plane"></i> Push Selected</>}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Toasts */}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            <i className={`fas ${t.type === 'success' ? 'fa-check-circle' : t.type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}`}></i>
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );
}

export default Dashboard;
