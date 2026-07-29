"""Fix remaining template issues - app_dept_id for scholarship, hod, transport, accounts."""
import re
import os

base = r'C:\Users\HP LAPTOP\OneDrive\Desktop\nodues-flow-ai\backend\templates'

# Fix scholarship - 3 param version (app_id, name, appNo) -> 4 params
fp = os.path.join(base, 'scholarship', 'dashboard.html')
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 3-param openModal to 4-param with app_dept_id
content = re.sub(
    r"openModal\('\$\{app\.application_id\}',\s*'\$\{app\.student_name\}',\s*'\$\{app\.application_number\}'\)",
    "openModal('${app.app_dept_id}', '${app.student_name}', '${app.application_number}', '${app.application_id}')",
    content
)

# Fix 2-param (old) openModal to include new appId param
content = re.sub(
    r"function openModal\(id,\s*name,\s*appNo\)",
    "function openModal(id, name, appNo, appId)",
    content
)

# Fix the body - add currentApplicationId = appId
content = content.replace(
    "function openModal(id, name, appNo, appId) { currentAppDeptId = id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('schDocsSection').style.display = 'none'; document.getElementById('actionModal').style.display = 'flex'; }",
    "function openModal(id, name, appNo, appId) { currentAppDeptId = id; currentApplicationId = appId || id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('schDocsSection').style.display = 'none'; loadSchDocs(appId || id); document.getElementById('actionModal').style.display = 'flex'; }"
)

# Add loadSchDocs function if not present
if 'function loadSchDocs' not in content:
    content = content.replace(
        "function closeModal()",
        "async function loadSchDocs(appId){const dv=document.getElementById('schDocsList');if(!dv)return;try{const t=localStorage.getItem('access_token');const r=await fetch(`/student/api/documents/${appId}`,{headers:{'Authorization':`Bearer ${t}`}});const d=await r.json();if(d.success&&d.data.length>0){dv.innerHTML=d.data.map(doc=>`<div style=\"display:flex;justify-content:space-between;padding:0.35rem 0;border-bottom:1px solid var(--border-light);font-size:0.8rem;\"><span>${doc.file_name}</span><span class=\"badge badge-${doc.status==='verified'?'success':'pending'}\">${doc.status}</span></div>`).join('')}else{dv.innerHTML='<span style=\"color:var(--text-muted);\">No documents uploaded</span>'}}catch(e){dv.innerHTML='Error loading docs'}}\n        function closeModal()"
    )

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed scholarship')

# Fix hod
fp = os.path.join(base, 'hod', 'dashboard.html')
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(
    r"openModal\('\$\{app\.application_id\}',\s*'\$\{app\.student_name\}',\s*'\$\{app\.application_number\}'\)",
    "openModal('${app.app_dept_id}', '${app.student_name}', '${app.application_number}', '${app.application_id}')",
    content
)

content = re.sub(
    r"function openModal\(id,\s*name,\s*appNo\)",
    "function openModal(id, name, appNo, appId)",
    content
)

content = content.replace(
    "function openModal(id, name, appNo, appId) { currentAppDeptId = id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('hodDocsSection').style.display = 'none'; document.getElementById('actionModal').style.display = 'flex'; }",
    "function openModal(id, name, appNo, appId) { currentAppDeptId = id; currentApplicationId = appId || id; document.getElementById('modalTitle').textContent = `Process: ${name}`; document.getElementById('modalAppInfo').textContent = `Application: ${appNo}`; document.getElementById('hodDocsSection').style.display = 'none'; loadHodDocs(appId || id); document.getElementById('actionModal').style.display = 'flex'; }"
)

if 'function loadHodDocs' not in content:
    content = content.replace(
        "function closeAppModal() {" if "function closeAppModal()" in content else "function closeModal()",
        "async function loadHodDocs(appId){const dv=document.getElementById('hodDocsList');if(!dv)return;try{const t=localStorage.getItem('access_token');const r=await fetch(`/student/api/documents/${appId}`,{headers:{'Authorization':`Bearer ${t}`}});const d=await r.json();if(d.success&&d.data.length>0){dv.innerHTML=d.data.map(doc=>`<div style=\"display:flex;justify-content:space-between;padding:0.35rem 0;border-bottom:1px solid var(--border-light);font-size:0.8rem;\"><span>${doc.file_name}</span><span class=\"badge badge-${doc.status==='verified'?'success':'pending'}\">${doc.status}</span></div>`).join('')}else{dv.innerHTML='<span style=\"color:var(--text-muted);\">No documents uploaded</span>'}}catch(e){dv.innerHTML='Error loading docs'}}\n        function closeModal()"
    )

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed hod')

# Fix transport
fp = os.path.join(base, 'transport', 'dashboard.html')
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(
    r"openModal\('\$\{app\.application_id\}',\s*'\$\{app\.student_name\}',\s*'\$\{app\.application_number\}'\)",
    "openModal('${app.app_dept_id}', '${app.student_name}', '${app.application_number}', '${app.application_id}')",
    content
)

content = re.sub(
    r"function openModal\(id,\s*name,\s*appNo\)",
    "function openModal(id, name, appNo, appId)",
    content
)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed transport')

print('All done!')
