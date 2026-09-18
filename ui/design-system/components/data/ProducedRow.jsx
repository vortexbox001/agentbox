const KIND_LABEL = { pull_request: 'Pull request', commit: 'Commit', file: 'File' };

export function ProducedRow({ kind, identifier, action }) {
  const children = [
    React.createElement('span', { key: 'k', className: 'ax-produced-kind' }, KIND_LABEL[kind] || kind),
    React.createElement('span', { key: 'i', className: 'ax-produced-id ax-mono' }, identifier),
  ];
  if (action) {
    children.push(React.createElement('a', {
      key: 'a', className: 'ax-btn ax-btn--ghost ax-btn--outlined', href: action,
      target: '_blank', rel: 'noopener',
    }, React.createElement('span', null, kind === 'file' ? 'Preview' : 'Open')));
  }
  return React.createElement('div', { className: 'ax-produced-row' }, children);
}
