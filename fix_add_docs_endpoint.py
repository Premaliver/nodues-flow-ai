"""Add documents API endpoint to student routes."""
fp = r'C:\Users\HP LAPTOP\OneDrive\Desktop\nodues-flow-ai\backend\blueprints\student\routes.py'

with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

old = """@student_bp.route("/api/apply", methods=["POST"])
@jwt_required()
@validate_json("selected_departments")
def create_application():"""

new = """@student_bp.route("/api/documents/<app_id>")
@jwt_required()
def get_application_documents(app_id):
    \"\"\"Get documents for an application (accessible by any authenticated department user).\"\"\"
    documents = Document.query.filter_by(application_id=app_id).all()
    return jsonify({
        "success": True,
        "data": [doc.to_dict() for doc in documents]
    })


@student_bp.route("/api/apply", methods=["POST"])
@jwt_required()
@validate_json("selected_departments")
def create_application():"""

content = content.replace(old, new)

with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)

print('Documents endpoint added to student routes!')
