export function Disclosure({ title, note, open = true, id, children, ...rest }) {
  const head = React.createElement('button', {
    type: 'button', className: 'ax-section-head', 'aria-expanded': open ? 'true' : 'false',
    'aria-controls': id ? `section-body-${id}` : undefined,
  }, [
    React.createElement('span', { key: 'chev', className: 'ax-section-chevron', 'aria-hidden': 'true' }),
    React.createElement('span', { key: 'title', className: 'ax-section-title' }, title),
    note ? React.createElement('span', { key: 'note', className: 'ax-section-note' }, note) : null,
  ]);
  const body = React.createElement('div', {
    className: 'ax-section-body', id: id ? `section-body-${id}` : undefined, hidden: !open,
  }, children);
  return React.createElement('section', {
    className: 'ax-section', 'data-section': '', 'data-section-id': id, ...rest,
  }, [head, body]);
}
