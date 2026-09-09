from flask import request


def page_args(default=25, maximum=100):
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(maximum, max(1, int(request.args.get('per_page', default))))
    except (TypeError, ValueError):
        per_page = default
    return page, per_page


def paginate_query(query, default=25, maximum=100):
    page, per_page = page_args(default, maximum)
    total = query.order_by(None).count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    pages = (total + per_page - 1) // per_page
    return items, {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': pages,
        'has_next': page < pages,
        'has_prev': page > 1,
    }
