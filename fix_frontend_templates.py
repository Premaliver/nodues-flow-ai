"""Fix department dashboard templates - use app_dept_id for process and add View Documents."""
import os

base = r'C:\Users\HP LAPTOP\OneDrive\Desktop\nodues-flow-ai\backend\templates'

# ===============================
# FIX 1: Hostel Dashboard
# ===============================
filepath = os.path.join(base, 'hostel', 'dashboard.html')
with open(filepath, 'r') as f:
    content = f.read()

# Fix 1: Use app_dept_id instead of application_id in the Process button
content = content.replace(
    "openHostelModal('${app.application_id}','${app.student_name}')",
    "openHostelModal('${app.app_dept_id}','${app.student_name}')"
)

# Fix 2: Add "View Documents" button in the modal and update modal to show docs
old_modal = '''    <div id="hostelModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.4);backdrop-filter:blur(8px);z-index:1000;align-items:center;justify-content:center;">
        <div class="card" style="width:100%;max-width:400px;padding:2rem;box-shadow:var(--shadow-xl);">
            <h3 style="font-family:'DM Serif Display',serif;font-size:1.15rem;font-weight:400;margin-bottom:1rem;" id="hostelModalTitle">Process Application</h3>
            <div style="display:flex;gap:1rem;margin-bottom:1rem;">
                <button class="btn btn-success" onclick="processHostel('approved')">✅ Approve</button>
                <button class="btn btn-danger" onclick="processHostel('rejected')">❌ Reject</button>
            </div>
            <div class="form-group"><label class="form-label">Remarks</label><textarea id="hostelRemarks" class="form-textarea" placeholder="Optional remarks..." style="min-height:80px;"></textarea></div>
            <button class="btn btn-ghost" onclick="document.getElementById('hostelModal').style.display='none'">Cancel</button>
        </div>'''

new_modal = '''    <div id="hostelModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.4);backdrop-filter:blur(8px);z-index:1000;align-items:center;justify-content:center;">
        <div class="card" style="width:100%;max-width:550px;padding:2rem;box-shadow:var(--shadow-xl);">
            <h3 style="font-family:'DM Serif Display',serif;font-size:1.15rem;font-weight:400;margin-bottom:1rem;" id="hostelModalTitle">Process Application</h3>
            <div id="hostelDocsSection" style="margin-bottom:1rem;padding:0.75rem;background:var(--bg-secondary);border-radius:var(--radius-lg);max-height:200px;overflow-y:auto;display:none;">
                <p style="font-size:0.85rem;font-weight:600;margin-bottom:0.5rem;">📄 Uploaded Documents</p>
                <div id="hostelDocsList"></div>
            <button class="btn btn-secondary btn-sm" onclick="viewHostelDocs()" style="margin-bottom:1rem;">📄 View Documents</button>
            <div style="display:flex;gap:1rem;margin-bottom:1rem;">
                <button class="btn btn-success" onclick="processHostel('approved')">✅ Approve</button>
                <button class="btn btn-danger" onclick="processHostel('rejected')">❌ Reject</button>
            </div>
            <div class="form-group"><label class="form-label">Remarks</label><textarea id="hostelRemarks" class="form-textarea" placeholder="Optional remarks..." style="min-height:80px;"></textarea></div>
            <button class="btn btn-ghost" onclick="document.getElementById('hostelModal').style.display='none'">Cancel</button>
        </div>'''

content = content.replace(old_modal, new_modal)

# Fix 3: Update JS - add viewHostelDocs function and change openHostelModal to take application_id
content = content.replace(
    'let hostelAppDeptId = null;',
    'let hostelAppDeptId = null;\n        let hostelApplicationId = null;'
)
content = content.replace(
    "function openHostelModal(id, name) { hostelAppDeptId = id; document.getElementById('hostelModalTitle').textContent = 'Process: '+name; document.getElementById('hostelModal').style.display = 'flex'; }",
    "function openHostelModal(id, name, appId) { hostelAppDeptId = id; hostelApplicationId = appId || id; document.getElementById('hostelModalTitle').textContent = 'Process: '+name; document.getElementById('hostelDocsSection').style.display = 'none'; document.getElementById('hostelModal').style.display = 'flex'; }\n\n        async function viewHostelDocs() {\n            if (!hostelApplicationId) return;\n            try {\n                const token = localStorage.getItem('access_token');\n                const res = await fetch(`/student/api/documents/${hostelApplicationId}`, { headers: { 'Authorization': `Bearer ${token}` } });\n                const d = await res.json();\n                const list = document.getElementById('hostelDocsList');\n                if (d.success && d.data.length > 0) {\n                    list.innerHTML = d.data.map(doc => `<div style="display:flex;justify-content:space-between;align-items:center;padding:0.35rem 0;border-bottom:1px solid var(--border-light);font-size:0.8rem;"><span>📄 ${doc.file_name}</span><span class="badge badge-${doc.status === 'verified' ? 'success' : doc.status === 'rejected' ? 'danger' : 'pending'}">${doc.status}</span></div>`).join('');\n                } else { list.innerHTML = '<p style="font-size:0.8rem;color:var(--text-muted);">No documents uploaded yet.</p>'; }\n                document.getElementById('hostelDocsSection').style.display = 'block';\n            } catch(e) { console.error(e); alert('Error loading documents'); }\n        }"
)

with open(filepath, 'w') as f:
    f.write(content)
print('✓ Updated hostel dashboard')


# ===============================
# FIX 2: Mess Dashboard
# ===============================
filepath = os.path.join(base, 'mess', 'dashboard.html')
with open(filepath, 'r') as f:
    content = f.read()

# Fix process button
content = content.replace(
    "openMessModal('${app.application_id}','${app.student_name}')",
    "openMessModal('${app.app_dept_id}','${app.student_name}','${app.application_id}')"
)

# Add applicationId var and modal
content = content.replace(
    'let messAppDeptId = null;',
    'let messAppDeptId = null;\n        let messApplicationId = null;'
)
content = content.replace(
    "function openMessModal(id, name) { messAppDeptId = id; document.getElementById('messModalTitle').textContent = 'Process: '+name; document.getElementById('messModal').style.display = 'flex'; }",
    "function openMessModal(id, name, appId) { messAppDeptId = id; messApplicationId = appId || id; document.getElementById('messModalTitle').textContent = 'Process: '+name; document.getElementById('messDocsSection').style.display = 'none'; document.getElementById('messModal').style.display = 'flex'; }\n        async function viewMessDocs() {\n            if (!messApplicationId) return;\n            try {\n                const token = localStorage.getItem('access_token');\n                const res = await fetch(`/student/api/documents/${messApplicationId}`, { headers: { 'Authorization': `Bearer ${token}` } });\n                const d = await res.json();\n                const list = document.getElementById('messDocsList');\n                if (d.success && d.data.length > 0) {\n                    list.innerHTML = d.data.map(doc => `<div style=\"display:flex;justify-content:space-between;align-items:center;padding:0.35rem 0;border-bottom:1px solid var(--border-light);font-size:0.8rem;\"><span>📄 ${doc.file_name}</span><span class=\"badge badge-${doc.status === 'verified' ? 'success' : doc.status === 'rejected' ? 'danger' : 'pending'}\">${doc.status}</span></div>`).join('');\n                } else { list.innerHTML = '<p style=\"font-size:0.8rem;color:var(--text-muted);\">No documents uploaded yet.</p>'; }\n                document.getElementById('messDocsSection').style.display = 'block';\n            } catch(e) { console.error(e); alert('Error loading documents'); }\n        }"
)

# Add docs section to modal
old_mess_modal = '''    <div id="messModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.4);backdrop-filter:blur(8px);z-index:1000;align-items:center;justify-content:center;">
        <div class="card" style="width:100%;max-width:400px;padding:2rem;box-shadow:var(--shadow-xl);">
            <h3 style="font-family:'DM Serif Display',serif;font-size:1.15rem;font-weight:400;margin-bottom:1rem;" id="messModalTitle">Process Application</h3>
            <div style="display:flex;gap:1rem;margin-bottom:1rem;">
                <button class="btn btn-success" onclick="processMess('approved')">✅ Approve</button>
                <button class="btn btn-danger" onclick="processMess('rejected')">❌ Reject</button>
            </div>
            <div class="form-group"><label class="form-label">Remarks</label><textarea id="messRemarks" class="form-textarea" style="min-height:80px;"></textarea></div>
            <button class="btn btn-ghost" onclick="document.getElementById('messModal').style.display='none'">Cancel</button>
        </div>'''

new_mess_modal = '''    <div id="messModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.4);backdrop-filter:blur(8px);z-index:1000;align-items:center;justify-content:center;">
        <div class="card" style="width:100%;max-width:550px;padding:2rem;box-shadow:var(--shadow-xl);">
            <h3 style="font-family:'DM Serif Display',serif;font-size:1.15rem;font-weight:400;margin-bottom:1rem;" id="messModalTitle">Process Application</h3>
            <div id="messDocsSection" style="margin-bottom:1rem;padding:0.75rem;background:var(--bg-secondary);border-radius:var(--radius-lg);max-height:200px;overflow-y:auto;display:none;">
                <p style="font-size:0.85rem;font-weight:600;margin-bottom:0.5rem;">📄 Uploaded Documents</p>
                <div id="messDocsList"></div>
            <button class="btn btn-secondary btn-sm" onclick="viewMessDocs()" style="margin-bottom:1rem;">📄 View Documents</button>
            <div style="display:flex;gap:1rem;margin-bottom:1rem;">
                <button class="btn btn-success" onclick="processMess('approved')">✅ Approve</button>
                <button class="btn btn-danger" onclick="processMess('rejected')">❌ Reject</button>
            </div>
            <div class="form-group"><label class="form-label">Remarks</label><textarea id="messRemarks" class="form-textarea" style="min-height:80px;"></textarea></div>
            <button class="btn btn-ghost" onclick="document.getElementById('messModal').style.display='none'">Cancel</button>
        </div>'''

content = content.replace(old_mess_modal, new_mess_modal)
with open(filepath, 'w') as f:
    f.write(content)
print('✓ Updated mess dashboard')


# ===============================
# FIX 3: Transport Dashboard
# ===============================
filepath = os.path.join(base, 'transport', 'dashboard.html')
with open(filepath, 'r') as f:
    content = f.read()

content = content.replace(
    "openModal('${app.application_id}', '${app.student_name}', '${app.application_number}')",
    "openModal('${app.app_dept_id}', '${app.student_name}', '${app.application_number}', '${app.application_id}')"
)

content = content.replace(
    'let currentAppDeptId = null;',
    'let currentAppDeptId = null;\n        let currentApplicationId = null;'
)

content = content.replace(
    "function openModal(id, name, appNo) { currentAppDeptId = id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('actionModal').style.display = 'flex'; }",
    "function openModal(id, name, appNo, appId) { currentAppDeptId = id; currentApplicationId = appId || id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('docsSection').style.display = 'none'; document.getElementById('actionModal').style.display = 'flex'; }"
)

# Add view docs function
content = content.replace(
    "function closeModal()",
    "async function viewApplicationDocs() { if (!currentApplicationId) return; try { const token = localStorage.getItem('access_token'); const res = await fetch(`/student/api/documents/${currentApplicationId}`, { headers: { 'Authorization': `Bearer ${token}` } }); const d = await res.json(); const list = document.getElementById('docsList'); if (d.success && d.data.length > 0) { list.innerHTML = d.data.map(doc => `<div style=\"display:flex;justify-content:space-between;align-items:center;padding:0.35rem 0;border-bottom:1px solid var(--border-light);font-size:0.8rem;\"><span>📄 ${doc.file_name}</span><span class=\"badge badge-${doc.status === 'verified' ? 'success' : doc.status === 'rejected' ? 'danger' : 'pending'}\">${doc.status}</span></div>`).join(''); } else { list.innerHTML = '<p style=\"font-size:0.8rem;color:var(--text-muted);\">No documents uploaded yet.</p>'; } document.getElementById('docsSection').style.display = 'block'; } catch(e) { console.error(e); alert('Error loading documents'); } }\n        function closeModal()"
)

# Add docs section to modal
old_transport_modal = '''    <div id="actionModal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); backdrop-filter: blur(8px); z-index: 1000; align-items: center; justify-content: center;">
        <div class="card" style="width: 100%; max-width: 450px; padding: 2rem; box-shadow: var(--shadow-xl);">
            <h3 style="font-family: 'DM Serif Display', serif; font-size: 1.15rem; font-weight: 400; margin-bottom: 0.5rem;" id="modalTitle">Process Application</h3>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem; font-size: 0.85rem;" id="modalAppInfo"></p>
            <div class="form-group"><div style="display: flex; gap: 1rem;">
                <button class="btn btn-success" onclick="processApplication('approved')">✅ Approve</button>
                <button class="btn btn-danger" onclick="processApplication('rejected')">❌ Reject</button>
            </div>
            <div class="form-group"><label class="form-label">Remarks</label><textarea id="modalRemarks" class="form-textarea" placeholder="Add remarks..." style="min-height: 80px;"></textarea></div>
            <div style="display: flex; gap: 0.5rem; justify-content: flex-end;"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button></div>
    </div>'''

new_transport_modal = '''    <div id="actionModal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); backdrop-filter: blur(8px); z-index: 1000; align-items: center; justify-content: center;">
        <div class="card" style="width: 100%; max-width: 550px; padding: 2rem; box-shadow: var(--shadow-xl);">
            <h3 style="font-family: 'DM Serif Display', serif; font-size: 1.15rem; font-weight: 400; margin-bottom: 0.5rem;" id="modalTitle">Process Application</h3>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem; font-size: 0.85rem;" id="modalAppInfo"></p>
            <div id="docsSection" style="margin-bottom:1rem;padding:0.75rem;background:var(--bg-secondary);border-radius:var(--radius-lg);max-height:200px;overflow-y:auto;display:none;">
                <p style="font-size:0.85rem;font-weight:600;margin-bottom:0.5rem;">📄 Uploaded Documents</p>
                <div id="docsList"></div>
            <button class="btn btn-secondary btn-sm" onclick="viewApplicationDocs()" style="margin-bottom:1rem;">📄 View Documents</button>
            <div class="form-group"><div style="display: flex; gap: 1rem;">
                <button class="btn btn-success" onclick="processApplication('approved')">✅ Approve</button>
                <button class="btn btn-danger" onclick="processApplication('rejected')">❌ Reject</button>
            </div>
            <div class="form-group"><label class="form-label">Remarks</label><textarea id="modalRemarks" class="form-textarea" placeholder="Add remarks..." style="min-height: 80px;"></textarea></div>
            <div style="display: flex; gap: 0.5rem; justify-content: flex-end;"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button></div>
    </div>'''

content = content.replace(old_transport_modal, new_transport_modal)
with open(filepath, 'w') as f:
    f.write(content)
print('✓ Updated transport dashboard')


# ===============================
# FIX 4: Scholarship Dashboard
# ===============================
filepath = os.path.join(base, 'scholarship', 'dashboard.html')
with open(filepath, 'r') as f:
    content = f.read()

content = content.replace(
    "openModal('${app.application_id}', '${app.student_name}', '${app.application_number}')",
    "openModal('${app.app_dept_id}', '${app.student_name}', '${app.application_number}', '${app.application_id}')"
)

content = content.replace(
    'let currentAppDeptId = null;',
    'let currentAppDeptId = null;\n        let currentApplicationId = null;'
)

content = content.replace(
    "function openModal(id, name, appNo) { currentAppDeptId = id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('actionModal').style.display = 'flex'; }",
    "function openModal(id, name, appNo, appId) { currentAppDeptId = id; currentApplicationId = appId || id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('schDocsSection').style.display = 'none'; document.getElementById('actionModal').style.display = 'flex'; }"
)

content = content.replace(
    "function closeModal()",
    "async function viewSchDocs() { if (!currentApplicationId) return; try { const token = localStorage.getItem('access_token'); const res = await fetch(`/student/api/documents/${currentApplicationId}`, { headers: { 'Authorization': `Bearer ${token}` } }); const d = await res.json(); const list = document.getElementById('schDocsList'); if (d.success && d.data.length > 0) { list.innerHTML = d.data.map(doc => `<div style=\"display:flex;justify-content:space-between;align-items:center;padding:0.35rem 0;border-bottom:1px solid var(--border-light);font-size:0.8rem;\"><span>📄 ${doc.file_name}</span><span class=\"badge badge-${doc.status === 'verified' ? 'success' : doc.status === 'rejected' ? 'danger' : 'pending'}\">${doc.status}</span></div>`).join(''); } else { list.innerHTML = '<p style=\"font-size:0.8rem;color:var(--text-muted);\">No documents uploaded yet.</p>'; } document.getElementById('schDocsSection').style.display = 'block'; } catch(e) { console.error(e); alert('Error loading documents'); } }\n        function closeModal()"
)

old_sch_modal = '''    <div id="actionModal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); backdrop-filter: blur(8px); z-index: 1000; align-items: center; justify-content: center;">
        <div class="card" style="width: 100%; max-width: 450px; padding: 2rem; box-shadow: var(--shadow-xl);">
            <h3 style="font-family: 'DM Serif Display', serif; font-size: 1.15rem; font-weight: 400; margin-bottom: 0.5rem;" id="modalTitle">Process Application</h3>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem; font-size: 0.85rem;" id="modalAppInfo"></p>
            <div class="form-group"><div style="display: flex; gap: 1rem;">
                <button class="btn btn-success" onclick="processApplication('approved')">✅ Approve</button>
                <button class="btn btn-danger" onclick="processApplication('rejected')">❌ Reject</button>
            </div>
            <div class="form-group"><label class="form-label">Remarks</label><textarea id="modalRemarks" class="form-textarea" placeholder="Add remarks..." style="min-height: 80px;"></textarea></div>
            <div style="display: flex; gap: 0.5rem; justify-content: flex-end;"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button></div>
    </div>'''

new_sch_modal = '''    <div id="actionModal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); backdrop-filter: blur(8px); z-index: 1000; align-items: center; justify-content: center;">
        <div class="card" style="width: 100%; max-width: 550px; padding: 2rem; box-shadow: var(--shadow-xl);">
            <h3 style="font-family: 'DM Serif Display', serif; font-size: 1.15rem; font-weight: 400; margin-bottom: 0.5rem;" id="modalTitle">Process Application</h3>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem; font-size: 0.85rem;" id="modalAppInfo"></p>
            <div id="schDocsSection" style="margin-bottom:1rem;padding:0.75rem;background:var(--bg-secondary);border-radius:var(--radius-lg);max-height:200px;overflow-y:auto;display:none;">
                <p style="font-size:0.85rem;font-weight:600;margin-bottom:0.5rem;">📄 Uploaded Documents</p>
                <div id="schDocsList"></div>
            <button class="btn btn-secondary btn-sm" onclick="viewSchDocs()" style="margin-bottom:1rem;">📄 View Documents</button>
            <div class="form-group"><div style="display: flex; gap: 1rem;">
                <button class="btn btn-success" onclick="processApplication('approved')">✅ Approve</button>
                <button class="btn btn-danger" onclick="processApplication('rejected')">❌ Reject</button>
            </div>
            <div class="form-group"><label class="form-label">Remarks</label><textarea id="modalRemarks" class="form-textarea" placeholder="Add remarks..." style="min-height: 80px;"></textarea></div>
            <div style="display: flex; gap: 0.5rem; justify-content: flex-end;"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button></div>
    </div>'''

content = content.replace(old_sch_modal, new_sch_modal)
with open(filepath, 'w') as f:
    f.write(content)
print('✓ Updated scholarship dashboard')


# ===============================
# FIX 5: HOD Dashboard
# ===============================
filepath = os.path.join(base, 'hod', 'dashboard.html')
with open(filepath, 'r') as f:
    content = f.read()

content = content.replace(
    "openModal('${app.application_id}', '${app.student_name}', '${app.application_number}')",
    "openModal('${app.app_dept_id}', '${app.student_name}', '${app.application_number}', '${app.application_id}')"
)

content = content.replace(
    'let currentAppDeptId = null;',
    'let currentAppDeptId = null;\n        let currentApplicationId = null;'
)

content = content.replace(
    "function openModal(id, name, appNo) { currentAppDeptId = id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('actionModal').style.display = 'flex'; }",
    "function openModal(id, name, appNo, appId) { currentAppDeptId = id; currentApplicationId = appId || id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('hodDocsSection').style.display = 'none'; document.getElementById('actionModal').style.display = 'flex'; }"
)

content = content.replace(
    "function closeModal()",
    "async function viewHodDocs() { if (!currentApplicationId) return; try { const token = localStorage.getItem('access_token'); const res = await fetch(`/student/api/documents/${currentApplicationId}`, { headers: { 'Authorization': `Bearer ${token}` } }); const d = await res.json(); const list = document.getElementById('hodDocsList'); if (d.success && d.data.length > 0) { list.innerHTML = d.data.map(doc => `<div style=\"display:flex;justify-content:space-between;align-items:center;padding:0.35rem 0;border-bottom:1px solid var(--border-light);font-size:0.8rem;\"><span>📄 ${doc.file_name}</span><span class=\"badge badge-${doc.status === 'verified' ? 'success' : doc.status === 'rejected' ? 'danger' : 'pending'}\">${doc.status}</span></div>`).join(''); } else { list.innerHTML = '<p style=\"font-size:0.8rem;color:var(--text-muted);\">No documents uploaded yet.</p>'; } document.getElementById('hodDocsSection').style.display = 'block'; } catch(e) { console.error(e); alert('Error loading documents'); } }\n        function closeModal()"
)

old_hod_modal = '''    <div id="actionModal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); backdrop-filter: blur(8px); z-index: 1000; align-items: center; justify-content: center;">
        <div class="card" style="width: 100%; max-width: 450px; padding: 2rem; box-shadow: var(--shadow-xl);">
            <h3 style="font-family: 'DM Serif Display', serif; font-size: 1.15rem; font-weight: 400; margin-bottom: 0.5rem;" id="modalTitle">Process Application</h3>
            <p style="color: var(--text-muted); margin-bottom: 1.5rem; font-size: 0.85rem;" id="modalAppInfo"></p>
            <div class="form-group"><div style="display: flex; gap: 1rem;">
                <button class="btn btn-success" onclick="processApplication('approved')">✅ Approve</button>
                <button class="btn btn-danger" onclick="processApplication('rejected')">❌ Reject</button>
            </div>
            <div class="form-group"><label class="form-label">Remarks</label><textarea id="modalRemarks" class="form-textarea" placeholder="Add remarks..." style="min-height: 80px;"></textarea></div>
            <div style="display: flex; gap: 0.5rem; justify-content: flex-end;"><button class="btn btn-ghost" onclick="closeModal()">Cancel</button></div>
    </div>'''

new_hod_modal = '''    <div id="actionModal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4); backdrop-filter: blur(8px); z-index: 1000; align-items: center; justify-content: center;">
        <div class="card" style="width: 100%; max-width: The multiple matches are causing issues. Let me use a python script approach for the templates too:

<execute_command>
<command>python -c "
import os, glob

templates_dir = r'C:\Users\HP LAPTOP\OneDrive\Desktop\nodues-flow-ai\backend\templates'
hostel = os.path.join(templates_dir, 'hostel', 'dashboard.html')

with open(hostel, 'r') as f:
    content = f.read()

# 1. Fix application_id -> app_dept_id in the onclick
content = content.replace(
    \"openHostelModal('\${app.application_id}','\${app.student_name}')\",
    \"openHostelModal('\${app.app_dept_id}','\${app.student_name}','\${app.application_id}')\"
)

# 2. Update openHostelModal to accept 3 params (appDeptId, studentName, appId)
content = content.replace(
    'function openHostelModal(id, name) { hostelAppDeptId = id; document.getElementById(\"hostelModalTitle\").textContent = \"Process: \"+name; document.getElementById(\"hostelModal\").style.display = \"flex\"; }',
    'function openHostelModal(id, name, appId) { hostelAppDeptId = id; document.getElementById(\"hostelModalTitle\").textContent = \"Process: \"+name; hostelViewAppId = appId; loadHostelDocs(appId); document.getElementById(\"hostelModal\").style.display = \"flex\"; }'
)

# 3. Add hostelViewAppId variable, loadDocs function, and docs section in modal
content = content.replace(
    'let hostelAppDeptId = null;',
    'let hostelAppDeptId = null; let hostelViewAppId = null;'
)

# 4. Add documents section and fetch function in the modal before Cancel button
content = content.replace(
    '<div class=\"form-group\"><label class=\"form-label\">Remarks</label><textarea id=\"hostelRemarks\" class=\"form-textarea\" placeholder=\"Optional remarks...\" style=\"min-height:80px;\"></textarea></div>',
    '<div class=\"form-group\"><label class=\"form-label\">Student Documents</label><div id=\"hostelDocsViewer\" style=\"background:var(--bg-secondary);border-radius:var(--radius-md);padding:0.75rem;margin-bottom:0.5rem;font-size:0.8rem;color:var(--text-muted);\">Loading docs...</div><div class=\"form-group\"><label class=\"form-label\">Remarks</label><textarea id=\"hostelRemarks\" class=\"form-textarea\" placeholder=\"Optional remarks...\" style=\"min-height:80px;\"></textarea></div>'
)

# 5. Add the loadHostelDocs function
content = content.replace(
    'function toggleTheme(){const h=document.documentElement;h.setAttribute(\"data-theme\",h.getAttribute(\"data-theme\")===\"dark\"?\"light\":\"dark\");}',
    'function toggleTheme(){const h=document.documentElement;h.setAttribute(\"data-theme\",h.getAttribute(\"data-theme\")===\"dark\"?\"light\":\"dark\");}\n        async function loadHostelDocs(appId){const dv=document.getElementById(\"hostelDocsViewer\");try{const t=localStorage.getItem(\"access_token\");const r=await fetch(`/student/api/documents/${appId}`,{headers:{\"Authorization\":`Bearer ${t}`}});const d=await r.json();if(d.success&&d.data.length>0){dv.innerHTML=d.data.map(doc=>`<div style=\"display:flex;justify-content:space-between;padding:0.35rem 0;border-bottom:1px solid var(--border-light);\"><span>${doc.document_type.replace(\"_\",\" \").replace(/_/g,\" \")}</span><span style=\"color:var(--text-muted);\">${doc.file_name}</span><span class=\"badge badge-${doc.status===\"verified\"?\"success\":\"pending\"}\">${doc.status}</span></div>`).join(\"\")}else{dv.innerHTML=\"<span style=\\\"color:var(--text-muted);\\\">No documents uploaded</span>\"}}catch(e){dv.innerHTML=\"Error loading documents\";console.error(e)}}'
)

with open(hostel, 'w') as f:
    f.write(content)
print('Hostel dashboard updated!')
"
</command>
</execute_command>
