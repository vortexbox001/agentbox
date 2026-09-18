function IoRow({ label, text, overflow, lines, intent }) {
  return React.createElement('div', {
    className: 'ax-io-row' + (overflow ? ' is-overflow' : ''), 'data-io-row': '',
  }, [
    React.createElement('span', { key: 'l', className: 'ax-io-label' }, label),
    React.createElement('div', { key: 'b', className: 'ax-io-body' + (intent ? ' ax-io-body--' + intent : '') }, [
      React.createElement('div', { key: 'c', className: 'ax-io-content' }, text),
      overflow ? React.createElement('div', { key: 'f', className: 'ax-io-fade', 'aria-hidden': 'true' }) : null,
    ]),
    overflow ? React.createElement('button', {
      key: 't', type: 'button', className: 'ax-io-toggle', 'data-io-toggle': '', 'aria-expanded': 'false',
    }, `Show all ${lines} lines`) : null,
  ]);
}

export function ToolCard({ name, description, marker, in_text, out_text, in_overflow, out_overflow,
  in_lines, out_lines, is_diff, out_intent }) {
  const head = React.createElement('div', { className: 'ax-toolcard-head' }, [
    React.createElement('span', { key: 'n', className: 'ax-toolcard-name' }, name),
    description ? React.createElement('span', { key: 'd', className: 'ax-toolcard-desc' }, description) : null,
    marker ? React.createElement('span', { key: 'm', className: 'ax-toolcard-marker' }, marker) : null,
  ]);
  return React.createElement('div', { className: 'ax-toolcard', 'data-toolcard': '' }, [
    head,
    in_text ? React.createElement(IoRow, { key: 'in', label: 'IN', text: in_text, overflow: in_overflow, lines: in_lines }) : null,
    (out_text || is_diff) ? React.createElement(IoRow, {
      key: 'out', label: 'OUT', text: out_text, overflow: out_overflow, lines: out_lines, intent: out_intent,
    }) : null,
  ]);
}
