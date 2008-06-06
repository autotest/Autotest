from django.conf.urls.defaults import *
import os
from frontend import settings
from frontend.afe.feeds import feed

feeds = {
    'jobs' : feed.JobFeed
}

pattern_list = [(r'^(?:|noauth/)rpc/', 'frontend.afe.views.handle_rpc')]

debug_pattern_list = [
    (r'^model_doc/', 'frontend.afe.views.model_documentation'),
    # for GWT hosted mode
    (r'^(?P<forward_addr>autotest.*)', 'frontend.afe.views.gwt_forward'),
    # for GWT compiled files
    (r'^client/(?P<path>.*)$', 'django.views.static.serve',
     {'document_root': os.path.join(os.path.dirname(__file__), '..', 'client',
                                    'www')}),
    # redirect / to compiled client
    (r'^$', 'django.views.generic.simple.redirect_to',
     {'url': 'client/autotest.AfeClient/AfeClient.html'}),

    # redirect /tko to local apache server
    (r'^(?P<path>tko/.*)$',
     'frontend.afe.views.redirect_with_extra_data',
     {'url': 'http://%(server_name)s/%(path)s?%(getdata)s'}),

    # Job feeds
    (r'^feeds/(?P<url>.*)/$', 'frontend.afe.feeds.feed.feed_view',
     {'feed_dict': feeds})

]

if settings.DEBUG:
	pattern_list += debug_pattern_list

urlpatterns = patterns('', *pattern_list)
