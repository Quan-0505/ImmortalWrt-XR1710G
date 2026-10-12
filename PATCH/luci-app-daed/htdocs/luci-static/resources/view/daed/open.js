'use strict';
'require view';
'require uci';

return view.extend({
	load: function() { return uci.load('daed'); },
	render: function() {
		var listen = uci.get('daed', 'main', 'listen') || '0.0.0.0:2023';
		var match = listen.match(/:(\d+)$/);
		var port = match ? Number(match[1]) : 2023;
		if (port < 1 || port > 65535) port = 2023;
		var target = new URL(window.location.href);
		// Top-level navigation works from HTTPS LuCI without a mixed-content iframe.
		target.protocol = 'http:';
		target.port = String(port);
		target.pathname = '/';
		target.username = '';
		target.password = '';
		target.search = '';
		target.hash = '/';
		// Replace the launcher in history so Back returns to the previous LuCI page.
		window.location.replace(target.href);
		return E('div', {}, [
			E('h2', {}, [ 'daed · Go KDAE' ]),
			E('a', { 'class': 'cbi-button cbi-button-action', 'href': target.href }, [ _('Open management page') ])
		]);
	},
	handleSave: null,
	handleSaveApply: null,
	handleReset: null
});
