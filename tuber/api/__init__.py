from functools import partial
from flask import send_from_directory, send_file, request, jsonify, g
from tuber.models import *
from tuber.permissions import *
from tuber import app, db
from marshmallow import EXCLUDE

all_permissions = []

def check_matches(matches, row, env):
    for match in matches:
        if getattr(row, match) != env[match]:
            return False
    return True

def crud(schema, permissions, matches=[], event=0, badge=0, department=0, id=None):
    if isinstance(schema, dict):
        for key, val in schema.items():
            if request.method in val:
                schema = key
    for perm in permissions[request.method]:
        if not check_permission(perm, event=event, department=department):
            return "", 403
    model = schema.opts.model
    filters = []
    for match in matches:
        filters.append(getattr(model, match) == locals()[match])

    if id is None:
        if request.method == "GET":
            if 'full' in g.data and g.data['full'].lower() == "true":
                rows = db.session.query(model).filter(*filters).all()
                return jsonify(schema.dump(rows, many=True))
            rows = db.session.query(model.id).filter(*filters).all()
            return jsonify([x.id for x in rows])
        if request.method == "POST":
            row = model(event=event, **g.data)
            db.session.add(row)
            db.session.commit()
            return jsonify(schema.dump(row))
    else:
        if request.method == "GET":
            row = schema.get_instance({"id": id})
            if check_matches(matches, row, locals()):
                return jsonify(schema.dump(row))
        if request.method == "PATCH":
            old_row = schema.get_instance({"id": id})
            if not check_matches(matches, old_row, locals()):
                return "", 403
            object = schema.dump(old_row)
            object.update(g.data)
            db.session.delete(old_row)
            new_row = schema.load(object, unknown=EXCLUDE)
            if check_matches(matches, new_row, locals()):
                db.session.add(new_row)
                db.session.commit()
                return jsonify(schema.dump(new_row))
            return "",  403
        if request.method == "DELETE":
            row = schema.get_instance({"id": id})
            if not check_matches(matches, row, locals()):
                return "", 403
            db.session.delete(row)
            db.session.commit()
            return jsonify(schema.dump(row))

def register_crud(name, schema, methods=["GET", "POST", "PATCH", "DELETE"], permissions={}, url_scheme="event"):
    default_permissions = {
        "GET": [name+".read"],
        "POST": [name+".create"],
        "PATCH": [name+".update"],
        "DELETE": [name+".delete"],
    }
    default_permissions.update(permissions)

    url_schemes = {
        "event": {
            "base_url": f"/api/events/<int:event>/{name}",
            "matches": ['event'],
        },
        "badge": {
            "base_url": f"/api/events/<int:event>/badge/<int:badge>/{name}",
            "matches": ['event', 'badge'],
        },
        "department": {
            "base_url": f"/api/events/<int:event/department/<int:department>/{name}",
            "matches": ['event', 'department'],
        },
        "global": {
            "base_url": f"/api/{name}",
            "matches": [],
        },
    }
    scheme = url_schemes[url_scheme]
    collective_methods = [x for x in methods if x in ["GET", "POST"]]
    if collective_methods:
        app.add_url_rule(scheme['base_url'], f"rest_collective_{name}", partial(crud, schema, default_permissions, matches=scheme['matches']), methods=collective_methods)

    individual_methods = [x for x in methods if x in ["GET", "PATCH", "DELETE"]]
    if individual_methods:
        app.add_url_rule(scheme['base_url']+"/<int:id>", f"rest_individual_{name}", partial(crud, schema, default_permissions, matches=scheme['matches']), methods=individual_methods)

    for method in methods: 
        for permission in default_permissions[method]:
            if not permission in all_permissions:
                all_permissions.append(permission)

from .users import *
from .hotels import *
from .events import *
from .importer import *
from .emails import *
from .badges import *
