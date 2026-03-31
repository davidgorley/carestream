import React, { useState, useEffect, useCallback, useRef } from 'react';
import { getRooms, createRoom, updateRoom, deleteRoom, csvPreview, csvImport, csvTemplateUrl, getSettings, updateSettings } from '../api';

function Settings() {
  const [activeTab, setActiveTab] = useState('rooms');
  const [rooms, setRooms] = useState([]);
  const [settings, setSettings] = useState({});
  const [toasts, setToasts] = useState([]);

  // Room form
  const [showRoomModal, setShowRoomModal] = useState(false);
  const [editingRoom, setEditingRoom] = useState(null);
  const [roomForm, setRoomForm] = useState({ room_number: '', unit: '', ip_address: '' });

  // CSV import
  const [csvRows, setCsvRows] = useState(null);
  const [csvImporting, setCsvImporting] = useState(false);
  const csvInputRef = useRef(null);

  const addToast = (message, type = 'info') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 5000);
  };

  const loadRooms = useCallback(async () => {
    try { setRooms(await getRooms()); } catch (e) { console.error(e); }
  }, []);

  const loadSettings = useCallback(async () => {
    try { setSettings(await getSettings()); } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { loadRooms(); loadSettings(); }, [loadRooms, loadSettings]);

  const openRoomForm = (room = null) => {
    if (room) {
      setEditingRoom(room);
      setRoomForm({ room_number: room.room_number, unit: room.unit, ip_address: room.ip_address });
    } else {
      setEditingRoom(null);
      setRoomForm({ room_number: '', unit: '', ip_address: '' });
    }
    setShowRoomModal(true);
  };

  const saveRoom = async () => {
    if (!roomForm.room_number || !roomForm.unit || !roomForm.ip_address) {
      addToast('All fields are required', 'error');
      return;
    }
    try {
      if (editingRoom) {
        await updateRoom(editingRoom.id, roomForm);
        addToast(`${roomForm.room_number} updated`, 'success');
      } else {
        await createRoom(roomForm);
        addToast(`${roomForm.room_number} added`, 'success');
      }
      setShowRoomModal(false);
      loadRooms();
    } catch (e) { addToast(e.message, 'error'); }
  };

  const handleDeleteRoom = async (room) => {
    if (!window.confirm(`Delete ${room.room_number}?`)) return;
    try {
      await deleteRoom(room.id);
      addToast(`${room.room_number} deleted`, 'success');
      loadRooms();
    } catch (e) { addToast(e.message, 'error'); }
  };

  const handleCsvFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const result = await csvPreview(file);
      if (result.error) { addToast(result.error, 'error'); return; }
      setCsvRows(result.rows);
    } catch (err) { addToast('Failed to parse CSV', 'error'); }
    e.target.value = '';
  };

  const handleCsvImport = async () => {
    if (!csvRows || !csvRows.length) return;
    setCsvImporting(true);
    try {
      const result = await csvImport(csvRows);
      addToast(result.message, 'success');
      setCsvRows(null);
      loadRooms();
    } catch (e) { addToast(e.message, 'error'); }
    setCsvImporting(false);
  };

  const saveSettings = async () => {
    try {
      const result = await updateSettings(settings);
      addToast(result.message || 'Settings saved', 'success');
    } catch (e) { addToast(e.message, 'error'); }
  };

  return (
    <div>
      <div className="section-header">
        <h2><i className="fas fa-cog" style={{ marginRight: 8, color: 'var(--primary)' }}></i>Settings</h2>
      </div>

      <div className="sub-tabs">
        <button className={`sub-tab ${activeTab === 'rooms' ? 'active' : ''}`} onClick={() => setActiveTab('rooms')}>
          <i className="fas fa-door-open" style={{ marginRight: 6 }}></i>Room Management
        </button>
        <button className={`sub-tab ${activeTab === 'config' ? 'active' : ''}`} onClick={() => setActiveTab('config')}>
          <i className="fas fa-server" style={{ marginRight: 6 }}></i>Server Config
        </button>
      </div>

      {activeTab === 'rooms' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" onClick={() => openRoomForm()}>
                <i className="fas fa-plus"></i> Add Room
              </button>
              <button className="btn btn-secondary" onClick={() => csvInputRef.current?.click()}>
                <i className="fas fa-file-csv"></i> Import CSV
              </button>
              <input ref={csvInputRef} type="file" accept=".csv" hidden onChange={handleCsvFile} />
              <a href={csvTemplateUrl} className="btn btn-outline" download style={{ textDecoration: 'none' }}>
                <i className="fas fa-download"></i> Download Template
              </a>
            </div>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{rooms.length} rooms configured</span>
          </div>

          {/* CSV Preview */}
          {csvRows && (
            <div className="card" style={{ marginBottom: 16, border: '1px solid var(--warning)' }}>
              <h4 style={{ marginBottom: 12 }}>
                <i className="fas fa-file-csv" style={{ marginRight: 8, color: 'var(--warning)' }}></i>
                CSV Preview — {csvRows.length} rows
              </h4>
              <div className="table-container" style={{ maxHeight: 300, overflowY: 'auto' }}>
                <table>
                  <thead>
                    <tr><th>Room</th><th>Unit</th><th>IP Address</th><th>Action</th></tr>
                  </thead>
                  <tbody>
                    {csvRows.map((row, idx) => (
                      <tr key={idx}>
                        <td>{row.room}</td>
                        <td>{row.unit}</td>
                        <td>{row.ip}</td>
                        <td>
                          <span className={`badge ${row.action === 'update' ? 'badge-pushing' : 'badge-online'}`}>
                            {row.action}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button className="btn btn-primary" onClick={handleCsvImport} disabled={csvImporting}>
                  {csvImporting ? 'Importing...' : 'Confirm Import'}
                </button>
                <button className="btn btn-secondary" onClick={() => setCsvRows(null)}>Cancel</button>
              </div>
            </div>
          )}

          {/* Room Table */}
          <div className="card">
            {rooms.length === 0 ? (
              <div className="empty-state" style={{ padding: 30 }}>
                <i className="fas fa-door-open"></i>
                <p>No rooms configured yet. Add rooms manually or import a CSV.</p>
              </div>
            ) : (
              <div className="table-container">
                <table>
                  <thead>
                    <tr><th>Room Number</th><th>Unit</th><th>IP Address</th><th>Status</th><th style={{ width: 120 }}>Actions</th></tr>
                  </thead>
                  <tbody>
                    {rooms.map(r => (
                      <tr key={r.id}>
                        <td style={{ fontWeight: 500 }}>{r.room_number}</td>
                        <td>{r.unit}</td>
                        <td><code style={{ fontSize: 13 }}>{r.ip_address}</code></td>
                        <td><span className={`badge badge-${r.status || 'unknown'}`}>{r.status || 'unknown'}</span></td>
                        <td>
                          <div style={{ display: 'flex', gap: 6 }}>
                            <button className="btn btn-secondary btn-sm" onClick={() => openRoomForm(r)}>
                              <i className="fas fa-edit"></i>
                            </button>
                            <button className="btn btn-danger btn-sm" onClick={() => handleDeleteRoom(r)}>
                              <i className="fas fa-trash"></i>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'config' && (
        <div className="card">
          <h4 style={{ marginBottom: 20 }}>Server Configuration</h4>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 20 }}>
            These settings are saved to the .env file. Port changes require a container restart.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, maxWidth: 600 }}>
            {[
              { key: 'SERVER_IP', label: 'Server IP Address' },
              { key: 'ADB_PORT', label: 'ADB Port' },
              { key: 'MEDIA_PATH', label: 'Media Storage Path' },
              { key: 'HEARTBEAT_INTERVAL', label: 'Heartbeat Interval (seconds)' },
              { key: 'CARESTREAM_PORT', label: 'App Port (requires restart)' },
              { key: 'ADB_PUSH_DEST', label: 'ADB Push Destination' },
            ].map(field => (
              <div className="form-group" key={field.key}>
                <label>{field.label}</label>
                <input className="input" value={settings[field.key] || ''}
                  onChange={e => setSettings(prev => ({ ...prev, [field.key]: e.target.value }))} />
              </div>
            ))}
          </div>
          <button className="btn btn-primary" onClick={saveSettings} style={{ marginTop: 8 }}>
            <i className="fas fa-save"></i> Save Configuration
          </button>
        </div>
      )}

      {/* Room Modal */}
      {showRoomModal && (
        <div className="modal-overlay" onClick={() => setShowRoomModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 450 }}>
            <div className="modal-header">
              <h3>{editingRoom ? 'Edit Room' : 'Add Room'}</h3>
              <button className="modal-close" onClick={() => setShowRoomModal(false)}>×</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Room Number</label>
                <input className="input" placeholder="e.g., Room 224" value={roomForm.room_number}
                  onChange={e => setRoomForm(prev => ({ ...prev, room_number: e.target.value }))} />
              </div>
              <div className="form-group">
                <label>Unit</label>
                <input className="input" placeholder="e.g., ICU, Pediatrics" value={roomForm.unit}
                  onChange={e => setRoomForm(prev => ({ ...prev, unit: e.target.value }))} />
              </div>
              <div className="form-group">
                <label>IP Address</label>
                <input className="input" placeholder="e.g., 192.168.1.101" value={roomForm.ip_address}
                  onChange={e => setRoomForm(prev => ({ ...prev, ip_address: e.target.value }))} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowRoomModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={saveRoom}>
                <i className="fas fa-save"></i> {editingRoom ? 'Update' : 'Add'} Room
              </button>
            </div>
          </div>
        </div>
      )}

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

export default Settings;
