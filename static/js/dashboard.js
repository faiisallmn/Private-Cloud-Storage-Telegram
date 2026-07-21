    (() => {
        'use strict';

        // State
        const API = '/api/files';
        const AUTH_API = '/api/auth';
        let currentPath = '/';
        let currentView = 'grid';
        let currentFiles = [];
        let currentFolders = [];
        let ctxTargetFile = null;

        // Auth
        const token = localStorage.getItem('auth_token');
        if (!token) { window.location.href = '/'; }

        const authHeaders = () => ({
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        });

        const authHeadersRaw = () => ({
            'Authorization': `Bearer ${token}`,
        });

        // Load user info
        try {
            const user = JSON.parse(localStorage.getItem('user') || '{}');
            const avatar = document.getElementById('userAvatar');
            avatar.textContent = (user.username || 'U')[0].toUpperCase();
            avatar.title = user.username || 'User';
        } catch(e) {}

        // File Type Icons & Colors

        function getFileIcon(filename, mime) {
            const ext = (filename || '').split('.').pop().toLowerCase();
            const map = {
                pdf: ['bi-file-earmark-pdf-fill', '#ef4444'],
                doc: ['bi-file-earmark-word-fill', '#3b82f6'],
                docx: ['bi-file-earmark-word-fill', '#3b82f6'],
                xls: ['bi-file-earmark-excel-fill', '#22c55e'],
                xlsx: ['bi-file-earmark-excel-fill', '#22c55e'],
                ppt: ['bi-file-earmark-ppt-fill', '#f97316'],
                pptx: ['bi-file-earmark-ppt-fill', '#f97316'],
                jpg: ['bi-file-earmark-image-fill', '#a855f7'],
                jpeg: ['bi-file-earmark-image-fill', '#a855f7'],
                png: ['bi-file-earmark-image-fill', '#a855f7'],
                gif: ['bi-file-earmark-image-fill', '#a855f7'],
                bmp: ['bi-file-earmark-image-fill', '#a855f7'],
                mp4: ['bi-file-earmark-play-fill', '#ec4899'],
                avi: ['bi-file-earmark-play-fill', '#ec4899'],
                mkv: ['bi-file-earmark-play-fill', '#ec4899'],
                mp3: ['bi-file-earmark-music-fill', '#14b8a6'],
                zip: ['bi-file-earmark-zip-fill', '#eab308'],
                rar: ['bi-file-earmark-zip-fill', '#eab308'],
                '7z': ['bi-file-earmark-zip-fill', '#eab308'],
                tar: ['bi-file-earmark-zip-fill', '#eab308'],
                gz: ['bi-file-earmark-zip-fill', '#eab308'],
                py: ['bi-file-earmark-code-fill', '#3b82f6'],
                js: ['bi-file-earmark-code-fill', '#eab308'],
                html: ['bi-file-earmark-code-fill', '#f97316'],
                css: ['bi-file-earmark-code-fill', '#3b82f6'],
                json: ['bi-file-earmark-code-fill', '#22c55e'],
                csv: ['bi-file-earmark-spreadsheet-fill', '#22c55e'],
                txt: ['bi-file-earmark-text-fill', '#8b949e'],
            };
            return map[ext] || ['bi-file-earmark-fill', '#8b949e'];
        }

        function formatSize(bytes) {
            if (!bytes || bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
        }

        function formatDate(iso) {
            if (!iso) return '—';
            const d = new Date(iso);
            return d.toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' });
        }

        // LOAD FILES

        window.loadFiles = async function(folderPath = '/') {
            currentPath = folderPath;
            updateBreadcrumb(folderPath);
            updateNavActive();

            try {
                const res = await fetch(
                    `${API}/list?folder=${encodeURIComponent(folderPath)}`,
                    { headers: authHeaders() }
                );

                if (res.status === 401) { logout(true); return; }
                const data = await res.json();

                currentFiles = data.files || [];
                currentFolders = data.folders || [];

                renderFiles();
                updateFolderTree();
                document.getElementById('fileCount').textContent =
                    `${currentFolders.length + currentFiles.length} item`;
                document.getElementById('storageUsed').textContent = `${currentFiles.length} file`;

                // Simulate storage bar
                const pct = Math.min(currentFiles.length * 5, 100);
                document.getElementById('storageBar').style.width = pct + '%';
            } catch (err) {
                console.error('loadFiles error:', err);
                showToast('Gagal memuat file', 'error');
            }
        };

        // RENDER FILES

        function renderFiles() {
            renderGrid();
            renderList();
        }

        function renderGrid() {
            const grid = document.getElementById('filesGrid');
            if (currentFolders.length === 0 && currentFiles.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state" style="grid-column: 1/-1">
                        <i class="bi bi-cloud-slash"></i>
                        <h3>Belum ada file</h3>
                        <p>Upload file pertama Anda atau buat folder baru</p>
                    </div>`;
                return;
            }

            let html = '';

            // Folders first
            currentFolders.forEach(f => {
                html += `
                <div class="file-card folder" ondblclick="navigateTo('${f.path}')" oncontextmenu="showContextMenu(event, ${f.id}, '${f.name.replace(/'/g, "\\'")}', 'folder')">
                    <span class="file-card-icon"><i class="bi bi-folder-fill"></i></span>
                    <div class="file-card-name" title="${f.name}">${f.name}</div>
                    <div class="file-card-meta">${formatDate(f.created_at)}</div>
                </div>`;
            });

            // Files
            currentFiles.forEach(f => {
                const [icon, color] = getFileIcon(f.filename);
                html += `
                <div class="file-card" data-id="${f.id}" data-name="${f.filename}"
                     oncontextmenu="showContextMenu(event, ${f.id}, '${f.filename.replace(/'/g, "\\'")}', 'file')"
                     onclick="selectCard(this)">
                    <button class="file-card-menu" onclick="event.stopPropagation(); showContextMenu(event, ${f.id}, '${f.filename.replace(/'/g, "\\'")}', 'file')">
                        <i class="bi bi-three-dots-vertical"></i>
                    </button>
                    <span class="file-card-icon" style="color:${color}"><i class="bi ${icon}"></i></span>
                    <div class="file-card-name" title="${f.filename}">${f.filename}</div>
                    <div class="file-card-meta">${formatSize(f.file_size)}</div>
                    <div class="file-row-actions" style="margin-top:6px;justify-content:center">
                        <button class="file-row-btn" title="Favorit" onclick="event.stopPropagation(); toggleFavorite(${f.id})"><i class="bi ${f.is_favorite ? 'bi-star-fill' : 'bi-star'}" style="${f.is_favorite ? 'color:#eab308' : ''}"></i></button>
                        <button class="file-row-btn" title="Unduh" onclick="event.stopPropagation(); downloadFile(${f.id}, '${f.filename.replace(/'/g, "\\'")}')"><i class="bi bi-download"></i></button>
                    </div>
                </div>`;
            });

            grid.innerHTML = html;
        }

        function renderList() {
            const tbody = document.getElementById('filesTableBody');
            let html = '';

            currentFolders.forEach(f => {
                html += `
                <tr ondblclick="navigateTo('${f.path}')">
                    <td><div class="file-row-name"><i class="bi bi-folder-fill" style="color:var(--warning)"></i> ${f.name}</div></td>
                    <td>—</td>
                    <td>${formatDate(f.created_at)}</td>
                    <td>
                        <div class="file-row-actions">
                            <button class="file-row-btn danger" title="Hapus" onclick="event.stopPropagation(); deleteFolder(${f.id}, '${f.name.replace(/'/g, "\\'")}')"><i class="bi bi-trash3"></i></button>
                        </div>
                    </td>
                </tr>`;
            });

            currentFiles.forEach(f => {
                const [icon, color] = getFileIcon(f.filename);
                html += `
                <tr data-id="${f.id}">
                    <td><div class="file-row-name"><i class="bi ${icon}" style="color:${color}"></i> ${f.filename}</div></td>
                    <td>${formatSize(f.file_size)}</td>
                    <td>${formatDate(f.created_at)}</td>
                    <td>
                        <div class="file-row-actions">
                            <button class="file-row-btn" title="Favorit" onclick="event.stopPropagation(); toggleFavorite(${f.id})"><i class="bi ${f.is_favorite ? 'bi-star-fill' : 'bi-star'}" style="${f.is_favorite ? 'color:#eab308' : ''}"></i></button>
                            <button class="file-row-btn" title="Pindahkan" onclick="event.stopPropagation(); openMoveModal(${f.id}, '${f.filename.replace(/'/g, "\\'")}')"><i class="bi bi-folder-symlink"></i></button>
                            <button class="file-row-btn" title="Unduh" onclick="downloadFile(${f.id}, '${f.filename.replace(/'/g, "\\'")}')"><i class="bi bi-download"></i></button>
                            <button class="file-row-btn danger" title="Hapus" onclick="deleteFile(${f.id})"><i class="bi bi-trash3"></i></button>
                        </div>
                    </td>
                </tr>`;
            });

            if (!html) {
                html = `<tr><td colspan="4" class="text-center" style="padding:60px;color:var(--text-muted)">Belum ada file</td></tr>`;
            }

            tbody.innerHTML = html;
        }

        // VIEW TOGGLE

        window.setView = function(view) {
            currentView = view;
            document.getElementById('filesGrid').classList.toggle('active', view === 'grid');
            document.getElementById('filesList').classList.toggle('active', view === 'list');
            document.getElementById('btnGridView').classList.toggle('active', view === 'grid');
            document.getElementById('btnListView').classList.toggle('active', view === 'list');
        };

        window.selectCard = function(card) {
            document.querySelectorAll('.file-card').forEach(c => c.classList.remove('selected'));
            card.classList.add('selected');
        };

        // BREADCRUMB

        function updateBreadcrumb(path) {
            const nav = document.getElementById('breadcrumb');
            const parts = path.split('/').filter(Boolean);
            let html = `<span class="breadcrumb-item ${parts.length === 0 ? 'current' : ''}" onclick="navigateTo('/')">Semua File</span>`;

            let builtPath = '';
            parts.forEach((part, i) => {
                builtPath += '/' + part;
                const isLast = i === parts.length - 1;
                html += `<span class="breadcrumb-sep"><i class="bi bi-chevron-right"></i></span>`;
                html += `<span class="breadcrumb-item ${isLast ? 'current' : ''}" onclick="navigateTo('${builtPath}/')">${part}</span>`;
            });

            nav.innerHTML = html;
        }

        // NAVIGATION

        window.navigateTo = function(path) {
            currentSpecialView = null;
            loadFiles(path);
        };

        let currentSpecialView = null;

        function updateNavActive() {
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            if (currentSpecialView) {
                document.querySelector(`[data-nav="${currentSpecialView}"]`)?.classList.add('active');
            } else if (currentPath === '/') {
                document.querySelector('[data-nav="all"]')?.classList.add('active');
            }
        }

        function updateFolderTree() {
            const tree = document.getElementById('folderTree');
            if (currentFolders.length === 0) {
                tree.innerHTML = `<div style="padding:8px 12px 8px 24px;font-size:0.78rem;color:var(--text-muted)">Tidak ada folder</div>`;
                return;
            }
            tree.innerHTML = currentFolders.map(f => `
                <div class="folder-tree-item" onclick="navigateTo('${f.path}')">
                    <i class="bi bi-folder-fill"></i> ${f.name}
                </div>
            `).join('');
        }

        // UPLOAD FILE

        window.openUploadModal = function() {
            document.getElementById('uploadModal').classList.add('show');
            document.getElementById('uploadProgress').classList.remove('show');
        };

        window.closeUploadModal = function() {
            document.getElementById('uploadModal').classList.remove('show');
            if (window.cancelUploadConfirm) window.cancelUploadConfirm();
        };

        // Drop zone logic
        const modalDropZone = document.getElementById('modalDropZone');
        const fileInput = document.getElementById('fileInput');

        modalDropZone.addEventListener('click', () => fileInput.click());

        modalDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            modalDropZone.classList.add('dragover');
        });

        modalDropZone.addEventListener('dragleave', () => {
            modalDropZone.classList.remove('dragover');
        });

        modalDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            modalDropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) prepareUpload(e.dataTransfer.files[0]);
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) prepareUpload(fileInput.files[0]);
        });

        // Drag & drop on main file area
        const fileArea = document.getElementById('fileArea');

        fileArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            document.getElementById('dropOverlay').classList.add('show');
        });

        fileArea.addEventListener('dragleave', (e) => {
            if (!fileArea.contains(e.relatedTarget)) {
                document.getElementById('dropOverlay').classList.remove('show');
            }
        });

        fileArea.addEventListener('drop', (e) => {
            e.preventDefault();
            document.getElementById('dropOverlay').classList.remove('show');
            if (e.dataTransfer.files.length > 0) {
                openUploadModal();
                setTimeout(() => prepareUpload(e.dataTransfer.files[0]), 200);
            }
        });

        let pendingUploadFile = null;

        window.prepareUpload = function(file) {
            pendingUploadFile = file;
            document.getElementById('uploadConfirmSection').style.display = 'block';
            document.getElementById('uploadActionButtons').style.display = 'flex';
            document.getElementById('uploadProgressContainer').style.display = 'none';
            document.getElementById('uploadFileName').textContent = file.name;
            document.getElementById('uploadFileSize').textContent = formatSize(file.size);
            document.getElementById('modalDropZone').style.display = 'none';
        };

        window.cancelUploadConfirm = function() {
            pendingUploadFile = null;
            document.getElementById('uploadConfirmSection').style.display = 'none';
            document.getElementById('modalDropZone').style.display = 'block';
            fileInput.value = '';
        };

        window.startConfirmedUpload = function() {
            if (!pendingUploadFile) return;
            document.getElementById('uploadActionButtons').style.display = 'none';
            document.getElementById('uploadProgressContainer').style.display = 'block';
            uploadFile(pendingUploadFile);
        };

        // Upload function — real-time progress via XMLHttpRequest
        window.uploadFile = async function(file) {
            const bar = document.getElementById('progressBar');
            const status = document.getElementById('uploadStatus');
            const pctLabel = document.getElementById('progressPercent');
            const sizeInfo = document.getElementById('uploadSizeInfo');

            bar.style.width = '0%';
            bar.style.background = '';
            bar.classList.remove('complete');
            pctLabel.textContent = '0%';
            sizeInfo.textContent = '';
            status.innerHTML = '<div class="spinner-sm"></div><span>Mempersiapkan...</span>';

            const formData = new FormData();
            formData.append('file', file);
            formData.append('folder_path', currentPath);

            const chunkSizeInput = document.getElementById('chunkSizeInput');
            if (chunkSizeInput && chunkSizeInput.value) {
                formData.append('chunk_size_mb', chunkSizeInput.value);
            }

            const totalSize = file.size;

            const fmtMB = (bytes) => {
                if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
                return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
            };

            const xhr = new XMLHttpRequest();

            // — Real-time progress: browser → server —
            xhr.upload.addEventListener('progress', (e) => {
                if (!e.lengthComputable) return;
                const pct = Math.round((e.loaded / e.total) * 100);
                bar.style.width = pct + '%';
                pctLabel.textContent = pct + '%';
                sizeInfo.textContent = fmtMB(e.loaded) + ' / ' + fmtMB(e.total);
                status.innerHTML = '<div class="spinner-sm"></div><span>Mengirim data... ' + pct + '%</span>';
            });

            // — Upload selesai dikirim ke server, menunggu respons backend —
            xhr.upload.addEventListener('load', () => {
                bar.style.width = '100%';
                pctLabel.textContent = '100%';
                sizeInfo.textContent = fmtMB(totalSize) + ' / ' + fmtMB(totalSize);
                status.innerHTML = '<div class="spinner-sm"></div><span>Mengenkripsi & mengunggah ke Telegram...</span>';
            });

            // — Response dari server sudah diterima —
            xhr.addEventListener('load', () => {
                let data;
                try { data = JSON.parse(xhr.responseText); } catch (_) { data = {}; }

                if (xhr.status === 401) { logout(true); return; }

                if (xhr.status >= 200 && xhr.status < 300) {
                    bar.style.width = '100%';
                    bar.classList.add('complete');
                    pctLabel.textContent = '100%';
                    const chunkInfo = data.is_chunked ? ` (${data.total_chunks} chunk)` : '';
                    status.innerHTML = `<i class="bi bi-check-circle-fill" style="color:var(--success)"></i><span style="color:var(--success)">Upload berhasil${chunkInfo}</span>`;
                    sizeInfo.textContent = fmtMB(totalSize) + ' / ' + fmtMB(totalSize);
                    showToast(`"${file.name}" berhasil diupload`, 'success');
                    setTimeout(() => {
                        loadFiles(currentPath);
                        closeUploadModal();
                    }, 1500);
                } else {
                    bar.style.width = '100%';
                    bar.style.background = 'var(--danger)';
                    pctLabel.textContent = '✗';
                    status.innerHTML = `<i class="bi bi-x-circle-fill" style="color:var(--danger)"></i><span style="color:var(--danger)">${data.error || 'Upload gagal'}</span>`;
                    sizeInfo.textContent = '';
                }
            });

            // — Error koneksi —
            xhr.addEventListener('error', () => {
                bar.style.width = '100%';
                bar.style.background = 'var(--danger)';
                pctLabel.textContent = '✗';
                status.innerHTML = '<i class="bi bi-x-circle-fill" style="color:var(--danger)"></i><span style="color:var(--danger)">Koneksi gagal</span>';
                sizeInfo.textContent = '';
                showToast('Upload gagal. Periksa koneksi server.', 'error');
            });

            xhr.open('POST', `${API}/upload`);
            xhr.setRequestHeader('Authorization', `Bearer ${token}`);
            xhr.send(formData);
        };

        function tick(ms) { return new Promise(r => setTimeout(r, ms)); }

        // DOWNLOAD FILE

        window.downloadFile = async function(fileId, filename) {
            showToast('Mempersiapkan pengunduhan...', 'info');
            
            // Menggunakan pengunduhan bawaan browser agar file tidak ditampung di RAM.
            // Backend sudah dikonfigurasi untuk menerima JWT via query_string (?token=...)
            const url = `${API}/download/${fileId}?token=${token}`;
            
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        };


        // SPECIAL VIEWS (Recent & Favorites)

        window.showSpecialView = async function(view) {
            currentSpecialView = view;
            const endpoint = view === 'recent' ? 'recent' : 'favorites';
            const label = view === 'recent' ? 'Baru-baru Ini' : 'Favorit';

            try {
                const res = await fetch(`${API}/${endpoint}`, {
                    headers: authHeaders(),
                });
                if (res.status === 401) { logout(true); return; }
                const data = await res.json();

                currentFiles = data.files || [];
                currentFolders = [];
                renderFiles();
                updateNavActive();

                document.getElementById('breadcrumb').innerHTML =
                    `<span class="breadcrumb-item" onclick="navigateTo('/')">Semua File</span>` +
                    `<span class="breadcrumb-sep">/</span>` +
                    `<span class="breadcrumb-item current">${label}</span>`;
                document.getElementById('fileCount').textContent = `${currentFiles.length} file`;
            } catch (err) {
                console.error('Error:', err);
                showToast('Gagal memuat data', 'error');
            }
        };

        window.toggleFavorite = async function(fileId) {
            try {
                const res = await fetch(`${API}/${fileId}/favorite`, {
                    method: 'PUT',
                    headers: authHeaders(),
                });
                if (res.status === 401) { logout(true); return; }
                const data = await res.json();

                if (res.ok) {
                    showToast(data.is_favorite ? 'Ditambahkan ke favorit' : 'Dihapus dari favorit', 'success');
                    // Refresh view
                    if (currentSpecialView) {
                        showSpecialView(currentSpecialView);
                    } else {
                        loadFiles(currentPath);
                    }
                } else {
                    showToast(data.error || 'Gagal', 'error');
                }
            } catch (err) {
                console.error('Favorite error:', err);
                showToast('Gagal mengubah favorit', 'error');
            }
        };

        // DELETE FILE & FOLDER — Custom Confirm Modal

        let _confirmDeleteCallback = null;

        window.openConfirmDelete = function(title, message, onConfirm) {
            document.getElementById('confirmDeleteTitle').textContent = title;
            document.getElementById('confirmDeleteMessage').textContent = message;
            document.getElementById('confirmDeleteError').style.display = 'none';
            _confirmDeleteCallback = onConfirm;
            document.getElementById('confirmDeleteModal').classList.add('show');
        };

        window.closeConfirmDelete = function() {
            document.getElementById('confirmDeleteModal').classList.remove('show');
            document.getElementById('confirmDeleteError').style.display = 'none';
            _confirmDeleteCallback = null;
        };

        window.showDeleteError = function(msg) {
            const el = document.getElementById('confirmDeleteError');
            document.getElementById('confirmDeleteErrorText').textContent = msg;
            el.style.display = 'block';
        };

        window.executeConfirmDelete = function() {
            if (_confirmDeleteCallback) _confirmDeleteCallback();
        };

        window.deleteFile = function(fileId) {
            openConfirmDelete(
                'Hapus File?',
                'File yang dihapus tidak dapat dikembalikan. Yakin ingin melanjutkan?',
                async () => {
                    try {
                        const res = await fetch(`${API}/${fileId}`, {
                            method: 'DELETE',
                            headers: authHeaders(),
                        });

                        if (res.status === 401) { logout(true); return; }

                        const data = await res.json();
                        if (!res.ok) {
                            showDeleteError(data.error || 'Gagal menghapus file');
                            return;
                        }

                        closeConfirmDelete();
                        showToast(data.message || 'File dihapus', 'success');
                        loadFiles(currentPath);
                    } catch (err) {
                        console.error('Delete error:', err);
                        showDeleteError('Koneksi gagal. Periksa server Anda.');
                    }
                }
            );
        };

        // CREATE FOLDER

        window.openFolderModal = function() {
            document.getElementById('folderModal').classList.add('show');
            document.getElementById('folderError').style.display = 'none';
            setTimeout(() => document.getElementById('folderNameInput').focus(), 200);
        };

        window.closeFolderModal = function() {
            document.getElementById('folderModal').classList.remove('show');
            document.getElementById('folderNameInput').value = '';
            document.getElementById('folderError').style.display = 'none';
        };

        window.createFolder = async function() {
            const name = document.getElementById('folderNameInput').value.trim();
            const errDiv = document.getElementById('folderError');
            errDiv.style.display = 'none';
            
            if (!name) { 
                errDiv.innerHTML = '<i class="bi bi-exclamation-circle"></i> Nama folder wajib diisi';
                errDiv.style.display = 'block';
                return; 
            }

            try {
                const res = await fetch(`${API}/folders`, {
                    method: 'POST',
                    headers: authHeaders(),
                    body: JSON.stringify({ name, parent_path: currentPath }),
                });

                if (res.status === 401) { logout(true); return; }

                const data = await res.json();
                if (!res.ok) {
                    errDiv.innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${data.error || 'Gagal buat folder'}`;
                    errDiv.style.display = 'block';
                    return;
                }

                showToast(`Folder "${name}" dibuat`, 'success');
                closeFolderModal();
                loadFiles(currentPath);
            } catch (err) {
                console.error('Create folder error:', err);
                errDiv.innerHTML = '<i class="bi bi-wifi-off"></i> Gagal membuat folder. Periksa koneksi.';
                errDiv.style.display = 'block';
            }
        };

        // Enter key on folder input
        document.getElementById('folderNameInput').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') createFolder();
        });

        // SEARCH FILES

        let searchTimeout;
        document.getElementById('searchInput').addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const q = e.target.value.trim();

            if (!q) { loadFiles(currentPath); return; }

            searchTimeout = setTimeout(async () => {
                try {
                    const res = await fetch(
                        `${API}/search?q=${encodeURIComponent(q)}`,
                        { headers: authHeaders() }
                    );

                    if (res.status === 401) { logout(true); return; }
                    const data = await res.json();

                    currentFiles = data.results || [];
                    currentFolders = [];
                    renderFiles();
                    document.getElementById('fileCount').textContent =
                        `${currentFiles.length} hasil untuk "${q}"`;
                } catch (err) {
                    console.error('Search error:', err);
                }
            }, 350);
        });

        // CONTEXT MENU

        window.showContextMenu = function(e, itemId, itemName, itemType) {
            e.preventDefault();
            e.stopPropagation();
            ctxTargetFile = { id: itemId, name: itemName, type: itemType };

            const menu = document.getElementById('contextMenu');
            let html = '';
            
            if (itemType === 'file') {
                html += `<div class="ctx-item" onclick="ctxAction('download')"><i class="bi bi-download"></i> Unduh</div>`;
                html += `<div class="ctx-item" onclick="ctxAction('favorite')"><i class="bi bi-star"></i> Favorit</div>`;
                html += `<div class="ctx-item" onclick="ctxAction('move')"><i class="bi bi-folder-symlink"></i> Pindahkan</div>`;
                html += `<div class="ctx-divider"></div>`;
                html += `<div class="ctx-item danger" onclick="ctxAction('delete')"><i class="bi bi-trash3"></i> Hapus</div>`;
            } else if (itemType === 'folder') {
                html += `<div class="ctx-item danger" onclick="ctxAction('delete_folder')"><i class="bi bi-trash3"></i> Hapus Folder</div>`;
            }

            menu.innerHTML = html;
            menu.classList.add('show');

            // Position
            const x = Math.min(e.clientX, window.innerWidth - 200);
            const y = Math.min(e.clientY, window.innerHeight - 120);
            menu.style.left = x + 'px';
            menu.style.top = y + 'px';
        };

        window.ctxAction = function(action) {
            const menu = document.getElementById('contextMenu');
            menu.classList.remove('show');
            if (!ctxTargetFile) return;

            if (action === 'favorite') {
                toggleFavorite(ctxTargetFile.id);
            } else if (action === 'download') {
                downloadFile(ctxTargetFile.id, ctxTargetFile.name);
                ctxTargetFile = null;
            } else if (action === 'delete') {
                deleteFile(ctxTargetFile.id);
                ctxTargetFile = null;
            } else if (action === 'move') {
                openMoveModal(ctxTargetFile.id, ctxTargetFile.name);
                // Do NOT clear ctxTargetFile here because move modal needs it
            } else if (action === 'delete_folder') {
                deleteFolder(ctxTargetFile.id, ctxTargetFile.name);
                ctxTargetFile = null;
            }
        };

        document.addEventListener('click', () => {
            document.getElementById('contextMenu').classList.remove('show');
        });

        // FOLDER DELETE & FILE MOVE

        window.deleteFolder = function(folderId, folderName) {
            openConfirmDelete(
                `Hapus Folder "${folderName}"?`,
                'Pastikan folder dalam keadaan kosong sebelum menghapus. Folder yang dihapus tidak dapat dikembalikan.',
                async () => {
                    try {
                        const res = await fetch(`${API}/folders/${folderId}`, {
                            method: 'DELETE',
                            headers: authHeaders()
                        });
                        if (res.status === 401) { logout(true); return; }
                        const data = await res.json();
                        if (!res.ok) {
                            showDeleteError(data.error || 'Gagal menghapus folder');
                            return;
                        }
                        closeConfirmDelete();
                        showToast(data.message || 'Folder dihapus', 'success');
                        loadFiles(currentPath);
                    } catch (err) {
                        console.error('Delete folder error:', err);
                        showDeleteError('Koneksi gagal. Periksa server Anda.');
                    }
                }
            );
        };

        window.openMoveModal = async function(fileId, filename) {
            ctxTargetFile = { id: fileId, name: filename, type: 'file' };
            
            try {
                const res = await fetch(`${API}/folders/all`, { headers: authHeaders() });
                if (res.status === 401) { logout(true); return; }
                const data = await res.json();
                
                const select = document.getElementById('moveFolderSelect');
                select.innerHTML = '<option value="/" style="color: #000;">/ (Root)</option>';
                if (data.folders) {
                    data.folders.forEach(f => {
                        select.innerHTML += `<option value="${f.path}" style="color: #000;">${f.path}</option>`;
                    });
                }
                
                document.getElementById('moveModal').classList.add('show');
            } catch (e) {
                console.error(e);
                showToast('Gagal memuat daftar folder', 'error');
            }
        };

        window.closeMoveModal = function() {
            document.getElementById('moveModal').classList.remove('show');
        };

        window.confirmMove = async function() {
            if (!ctxTargetFile) return;
            const targetPath = document.getElementById('moveFolderSelect').value;
            
            try {
                const res = await fetch(`${API}/${ctxTargetFile.id}/move`, {
                    method: 'PUT',
                    headers: {
                        ...authHeaders(),
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ folder_path: targetPath })
                });
                if (res.status === 401) { logout(true); return; }
                const data = await res.json();
                
                if (!res.ok) {
                    showToast(data.error || 'Gagal memindahkan file', 'error');
                    return;
                }
                
                showToast(data.message || 'File berhasil dipindahkan', 'success');
                closeMoveModal();
                ctxTargetFile = null;
                loadFiles(currentPath);
            } catch (e) {
                console.error(e);
                showToast('Terjadi kesalahan saat memindahkan file', 'error');
            }
        };

        // TOAST NOTIFICATIONS

        window.showToast = function(message, type = 'info') {
            const container = document.getElementById('toastContainer');
            const icons = {
                success: 'bi-check-circle-fill',
                error: 'bi-exclamation-circle-fill',
                info: 'bi-info-circle-fill',
            };

            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `<i class="bi ${icons[type]}"></i> ${message}`;
            container.appendChild(toast);

            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(40px)';
                toast.style.transition = 'all 0.3s ease';
                setTimeout(() => toast.remove(), 300);
            }, 3500);
        };

        // LOGOUT

        window.logout = async function(skipApiCall = false) {
            if (!skipApiCall) {
                try {
                    await fetch(`${AUTH_API}/logout`, {
                        method: 'POST',
                        headers: authHeaders(),
                    });
                } catch (e) {}
            }

            localStorage.removeItem('auth_token');
            localStorage.removeItem('user');
            window.location.href = '/';
        };

        // KEYBOARD SHORTCUTS

        document.addEventListener('keydown', (e) => {
            // Ctrl+K → focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('searchInput').focus();
            }
            // Escape → close modals
            if (e.key === 'Escape') {
                closeUploadModal();
                closeFolderModal();
                closeMoveModal();
                document.getElementById('contextMenu').classList.remove('show');
            }
        });

        // INIT

        loadFiles('/');

    })();
