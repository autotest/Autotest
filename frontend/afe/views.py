import urllib2

from frontend.afe import models, rpc_handler, rpc_interface, site_rpc_interface
from frontend.afe import rpc_utils
from django.http import HttpResponse, HttpResponsePermanentRedirect

# since site_rpc_interface is later in the list, its methods will override those
# of rpc_interface
rpc_handler_obj = rpc_handler.RpcHandler((rpc_interface, site_rpc_interface),
					 document_module=rpc_interface)


def handle_rpc(request):
	rpc_utils.set_user(request.afe_user)
	return rpc_handler_obj.handle_rpc_request(request)


def model_documentation(request):
	doc = '<h2>Models</h2>\n'
	for model_name in ('Label', 'Host', 'Test', 'User', 'AclGroup', 'Job'):
		model_class = getattr(models, model_name)
		doc += '<h3>%s</h3>\n' % model_name
		doc += '<pre>\n%s</pre>\n' % model_class.__doc__
	return HttpResponse(doc)


def redirect_with_extra_data(request, url, **kwargs):
	kwargs['getdata'] = request.GET.urlencode()
	kwargs['server_name'] = request.META['SERVER_NAME']
	return HttpResponsePermanentRedirect(url % kwargs)


GWT_SERVER = 'http://localhost:8888/'
def gwt_forward(request, forward_addr):
	if len(request.POST) == 0:
		data = None
	else:
		data = request.raw_post_data
	url_response = urllib2.urlopen(GWT_SERVER + forward_addr, data=data)
	http_response = HttpResponse(url_response.read())
	for header, value in url_response.info().items():
		if header not in ('connection',):
			http_response[header] = value
	return http_response
