// Clash Verge Rev 全局扩展脚本。规则库自动更新；不包含节点、账号或凭证。
// 国内域名库来源：https://github.com/MetaCubeX/meta-rules-dat
const chinaDirectDomains = [
  // 抖音、抖店、剪映、即梦及网页实际引用的资源域名。
  'douyin.com', 'douyinpic.com', 'douyincdn.com', 'iesdouyin.com',
  'jinritemai.com', 'jianying.com', 'capcut.cn', 'vlabstatic.com',
  'ulikecam.com', 'byteimg.com', 'ibyteimg.com', 'pstatp.com',
  'snssdk.com', 'bytedance.com', 'zijieapi.com', 'bytednsdoc.com',
  'ibytedapm.com', 'ecombdimg.com', 'ecombdstatic.com', 'ecombdapi.com',
  'yhgfb-cn-static.com',
  // LibTV 页面、接口及素材。
  'libtv.com', 'liblib.tv', 'liblib.art', 'liblib.cloud',
  // 国际站及国内经营工具。
  'alibaba.com', 'alicdn.com', 'aliimg.com', 'aliyuncs.com',
  '1688.com', 'taobao.com', 'dingtalk.com', 'chengji-inc.com',
  'sooxie.com', 'workbuddy.cn', 'codebuddy.cn',
];

function main(config) {
  const providerName = 'CN-Domains-Direct';
  config['rule-providers'] = config['rule-providers'] || {};
  config['rule-providers'][providerName] = {
    type: 'http', behavior: 'domain', format: 'mrs',
    url: 'https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geosite/cn.mrs',
    path: './RuleSet/cn-direct.mrs', interval: 86400,
  };
  const explicitRules = chinaDirectDomains.map(domain => 'DOMAIN-SUFFIX,' + domain + ',DIRECT');
  const domesticRules = explicitRules.concat([
    'RULE-SET,' + providerName + ',DIRECT',
    'DOMAIN-SUFFIX,cn,DIRECT',
    'DOMAIN-SUFFIX,xn--fiqs8s,DIRECT', // .中国
    'DOMAIN-SUFFIX,xn--fiqz9s,DIRECT', // .中國
  ]);
  const originalRules = config.rules || [];
  // 保留原有拒绝规则的优先级，避免国内规则库意外放行原本拦截的域名。
  const rejects = originalRules.filter(rule => /^REJECT(?:-DROP)?$/i.test(rule.split(',')[2] || ''));
  const rest = originalRules.filter(rule => !rejects.includes(rule) && !domesticRules.includes(rule));
  // IP 归属兜底放在域名规则之后；不使用 no-resolve，以覆盖缺少域名标签的国内目标。
  if (!rest.some(rule => /^GEOIP,CN,DIRECT(?:,|$)/i.test(rule))) {
    const finalIndex = rest.findIndex(rule => /^MATCH,/i.test(rule));
    rest.splice(finalIndex < 0 ? rest.length : finalIndex, 0, 'GEOIP,CN,DIRECT');
  }
  config.rules = Array.from(new Set(rejects.concat(domesticRules, rest)));
  const localDns = ['https://dns.alidns.com/dns-query#DIRECT', 'https://doh.pub/dns-query#DIRECT'];
  config.dns = config.dns || {};
  config.dns['nameserver-policy'] = config.dns['nameserver-policy'] || {};
  config.dns['nameserver-policy']['rule-set:' + providerName] = localDns;
  chinaDirectDomains.concat(['cn', 'xn--fiqs8s', 'xn--fiqz9s']).forEach(domain => {
    config.dns['nameserver-policy']['+.' + domain] = localDns;
  });
  config.dns['direct-nameserver'] = localDns;
  return config;
}
