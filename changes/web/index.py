import changes
import urlparse

from changes.config import statsreporter
from flask import render_template, current_app
from flask.views import MethodView


class IndexView(MethodView):
    custom_js = None
    custom_css = None

    def __init__(self, use_v2=False):
        self.use_v2 = use_v2
        super(MethodView, self).__init__()

    def get(self, path=''):
        statsreporter.stats().incr('homepage_view')
        if current_app.config['SENTRY_DSN'] and False:
            parsed = urlparse.urlparse(current_app.config['SENTRY_DSN'])
            dsn = '%s://%s@%s/%s' % (
                parsed.scheme.rsplit('+', 1)[-1],
                parsed.username,
                parsed.hostname + (':%s' % (parsed.port,) if parsed.port else ''),
                parsed.path,
            )
        else:
            dsn = None

        # variables to ship down to the webapp
        use_another_host = current_app.config['WEBAPP_USE_ANOTHER_HOST']

        # if we have custom js/css, we embed it in the html (making sure we
        # only do one file read).
        # TODO: we should link to files instead
        if current_app.config['WEBAPP_CUSTOM_JS'] and not IndexView.custom_js:
            IndexView.custom_js = open(current_app.config['WEBAPP_CUSTOM_JS']).read()

        if current_app.config['WEBAPP_CUSTOM_CSS'] and not IndexView.custom_css:
            IndexView.custom_css = open(current_app.config['WEBAPP_CUSTOM_CSS']).read()

        # use new react code
        if self.use_v2:
            return render_template('webapp.html', **{
                'SENTRY_PUBLIC_DSN': dsn,
                'RELEASE_INFO': changes.get_revision_info(),
                'WEBAPP_USE_ANOTHER_HOST': use_another_host,
                'WEBAPP_CUSTOM_JS': IndexView.custom_js,
                'WEBAPP_CUSTOM_CSS': IndexView.custom_css,
                'USE_PACKAGED_JS': not current_app.debug,
                'IS_DEBUG': current_app.debug
            })

        return render_template('index.html', **{
            'SENTRY_PUBLIC_DSN': dsn,
            'VERSION': changes.get_version(),
            'WEBAPP_USE_ANOTHER_HOST': use_another_host
        })
