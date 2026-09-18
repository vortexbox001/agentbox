const CHECK_META = {
  'pass': { cls: 'ax-result--pass', icon: 'check-circle' },
  'warn': { cls: 'ax-result--warn', icon: 'warn-tri' },
  'fail-blocking': { cls: 'ax-result--fail', icon: 'x-circle' },
  'not-run': { cls: '', icon: 'check-circle' },
};

export function CheckRow({ status, name, detail, recorded }) {
  const meta = CHECK_META[status] || CHECK_META['not-run'];
  const mark = React.createElement('span', { className: 'ax-result ' + meta.cls, role: 'img' },
    React.createElement('svg', { className: 'ax-icon', width: 16, height: 16, 'aria-hidden': 'true' },
      React.createElement('use', { href: '#' + meta.icon })));
  return React.createElement('div', { className: 'ax-checkrow' }, [
    React.createElement('span', { key: 'm', className: 'ax-checkrow-mark' }, mark),
    React.createElement('span', { key: 'n', className: 'ax-checkrow-name' }, name),
    React.createElement('span', { key: 'd', className: 'ax-checkrow-detail' }, detail || '—'),
    React.createElement('span', { key: 'r', className: 'ax-checkrow-time' }, recorded || '—'),
  ]);
}
