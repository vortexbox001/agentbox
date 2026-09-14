export function SchedulePill({ type = 'schedule', label, on = false, onToggle, style, ...rest }) {
  const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round', width: 12, height: 12, viewBox: '0 0 24 24' };
  const icon = type === 'sensor'
    ? React.createElement('svg', stroke, React.createElement('circle', { cx: 12, cy: 12, r: 2 }), React.createElement('path', { d: 'M7.76 16.24a6 6 0 0 1 0-8.49M16.24 7.76a6 6 0 0 1 0 8.49M4.93 19.07a10 10 0 0 1 0-14.14M19.07 4.93a10 10 0 0 1 0 14.14' }))
    : React.createElement('svg', stroke, React.createElement('circle', { cx: 12, cy: 12, r: 9 }), React.createElement('polyline', { points: '12 7 12 12 15 14' }));
  const wrap = { display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '4px 10px', borderRadius: '8px', background: 'var(--color-background-gray)', minWidth: 0, ...style };
  const track = { width: '22px', height: '13px', borderRadius: '999px', background: on ? 'var(--color-accent-teal)' : 'var(--color-border-default)', position: 'relative', flexShrink: 0, display: 'inline-block', cursor: onToggle ? 'pointer' : 'default' };
  const knob = { position: 'absolute', top: '2px', [on ? 'right' : 'left']: '2px', width: '9px', height: '9px', borderRadius: '50%', background: '#fff' };
  return React.createElement('span', { style: wrap, ...rest },
    React.createElement('span', { style: { color: 'var(--color-text-lighter)', display: 'inline-flex', flexShrink: 0 } }, icon),
    React.createElement('span', { style: { font: 'var(--type-body-sm)', color: 'var(--color-text-default)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, label),
    React.createElement('span', { style: track, onClick: onToggle, role: onToggle ? 'switch' : undefined, 'aria-checked': on }, React.createElement('span', { style: knob }))
  );
}
