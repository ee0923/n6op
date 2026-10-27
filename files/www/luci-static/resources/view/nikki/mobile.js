'use strict';
'require form';
'require view';
'require uci';

return view.extend({
    load: function () {
        return uci.load('nikki');
    },
    render: function () {
        const automatic = 'file:usb-mobile-auto.yaml';
        const phoneOnly = 'file:usb-mobile.yaml';
        const selected = uci.get('nikki', 'config', 'profile');

        if (selected !== automatic && selected !== phoneOnly) {
            this.handleSaveApply = null;
            this.handleSave = null;
            this.handleReset = null;
            return E('div', {}, [
                E('h2', {}, '手机分流'),
                E('p', {}, '请先在插件配置中选择 usb-mobile-auto.yaml，再设置自动回退。'),
                E('a', { 'class': 'cbi-button cbi-button-action', href: L.url('admin/services/nikki/config') }, '打开插件配置')
            ]);
        }

        const map = new form.Map('nikki', '手机分流',
            '指定域名优先使用手机，其他流量继续走网线。域名规则中的节点仍填写 MOBILE。');
        const section = map.section(form.NamedSection, 'config', 'config');
        const option = section.option(form.Flag, 'profile', '断网自动切回网线',
            '开启：USB 断开或手机无法上网时改用网线，手机恢复后重新优先使用手机。关闭：指定域名只走手机。保存并应用后生效。');
        option.enabled = automatic;
        option.disabled = phoneOnly;
        option.rmempty = false;
        option.description += '<br>仅在 Nikki 启用且本开关开启时，每 10 秒通过手机和网线分别请求 https://cp.cloudflare.com/generate_204；超时为 3 秒。此请求用于检查连通性，会产生少量流量。';
        option.description += '<br>切换针对新连接，已有下载、通话等连接可能需要重连。';
        return map.render();
    }
});
