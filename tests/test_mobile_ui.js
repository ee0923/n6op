'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'files/www/luci-static/resources/view/nikki/mobile.js'), 'utf8');

function loadPage(selected) {
    const reads = [];
    class Map {
        constructor(config) { this.config = config; this.options = []; }
        section(kind, name, type) {
            assert.equal(name, 'config');
            assert.equal(type, 'config');
            return { option: (kind, name, title, description) => {
                const option = { name, title, description };
                this.options.push(option);
                return option;
            } };
        }
        render() { return this; }
    }
    const form = { Map, NamedSection: 'named', Flag: 'flag' };
    const uci = {
        load: config => { reads.push(config); return Promise.resolve(); },
        get: (config, section, option) => {
            assert.deepEqual([config, section, option], ['nikki', 'config', 'profile']);
            return selected;
        }
    };
    const E = (tag, attributes, children) => ({ tag, attributes, children });
    const page = new Function('view', 'form', 'uci', 'E', 'L', source)(
        { extend: value => value }, form, uci, E, { url: value => '/' + value });
    return { page, reads, Map };
}

(async () => {
    for (const selected of ['file:usb-mobile-auto.yaml', 'file:usb-mobile.yaml']) {
        const { page, reads, Map } = loadPage(selected);
        await page.load();
        assert.deepEqual(reads, ['nikki']);
        const rendered = page.render();
        assert.ok(rendered instanceof Map);
        assert.equal(rendered.config, 'nikki');
        assert.equal(rendered.options.length, 1, 'The switch must only change the selected profile');
        const option = rendered.options[0];
        assert.equal(option.name, 'profile');
        assert.equal(option.enabled, 'file:usb-mobile-auto.yaml');
        assert.equal(option.disabled, 'file:usb-mobile.yaml');
        assert.equal(option.rmempty, false, 'Off must select phone-only mode, not delete the profile');
        assert.match(option.description, /https:\/\/cp\.cloudflare\.com\/generate_204/);
        assert.match(option.description, /10 秒/);
    }
    for (const selected of ['subscription:subscription', 'file:custom.yaml', undefined]) {
        const { page, Map } = loadPage(selected);
        const rendered = page.render();
        assert.equal(rendered instanceof Map, false, 'Unrelated profiles must not be overwritten');
        assert.equal(page.handleSaveApply, null);
        assert.equal(page.handleSave, null);
        assert.equal(page.handleReset, null);
    }
    const menu = JSON.parse(fs.readFileSync(path.join(root, 'files/usr/share/luci/menu.d/mobile-usb.json'), 'utf8'));
    const entry = menu['admin/services/nikki/mobile'];
    assert.equal(entry.action.path, 'nikki/mobile');
    assert.deepEqual(entry.depends.acl, ['luci-app-nikki']);
    assert.deepEqual(entry.depends.uci, { nikki: true });
    console.log('Mobile UI: both switch states and three unrelated-profile cases passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
