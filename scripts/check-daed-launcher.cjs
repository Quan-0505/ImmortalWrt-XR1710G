const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync(process.argv[2] || 'PATCH/luci-app-daed/htdocs/luci-static/resources/view/daed/open.js', 'utf8');
const cases = [
  ['http://192.168.2.1/cgi-bin/luci/admin/services/daed', undefined, 'http://192.168.2.1:2023/#/'],
  ['https://router.example:8443/cgi-bin/luci/?auth=fixture', '0.0.0.0:12023', 'http://router.example:12023/#/'],
  ['https://[fd00::1]/cgi-bin/luci/', '[::]:2023', 'http://[fd00::1]:2023/#/'],
  ['http://router.example/', '0.0.0.0:0', 'http://router.example:2023/#/'],
  ['http://router.example/', '0.0.0.0:70000', 'http://router.example:2023/#/'],
  ['http://fixture:fixture@router.example/cgi-bin/luci/', '0.0.0.0:2023', 'http://router.example:2023/#/'],
];
for (const [href, listen, expected] of cases) {
  let navigated;
  const page = new Function('view', 'uci', 'window', 'E', '_', source)(
    { extend: x => x },
    { load: () => Promise.resolve(), get: () => listen },
    { location: { href, replace: x => { navigated = x; } } },
    () => ({}), x => x,
  );
  page.render();
  assert.equal(navigated, expected);
}
const menu = JSON.parse(fs.readFileSync('PATCH/luci-app-daed/root/usr/share/luci/menu.d/luci-app-daed.json'));
assert.equal(menu['admin/services/daed'].action.path, 'daed/open');
console.log('PASS: LuCI service entry, IPv4/IPv6, HTTPS navigation, custom/invalid ports, query and basic-auth stripping.');
