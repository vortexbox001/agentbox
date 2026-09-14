export function Tabs({ children, selectedId, onChange, size = 'large', style, ...rest }) {
  const s = { display: 'flex', gap: '16px', fontSize: size === 'small' ? '12px' : '14px', lineHeight: '20px', fontWeight: 600, borderBottom: '1px solid var(--color-keyline-default)', ...style };
  return React.createElement('div', { role: 'tablist', style: s, ...rest },
    React.Children.map(children, child => {
      if (!React.isValidElement(child)) return null;
      return React.cloneElement(child, { selected: child.props.selected || child.props.id === selectedId, size, ...(onChange ? { onClick: () => onChange(child.props.id || '') } : {}) });
    })
  );
}

export function Tab({ id, selected, disabled, children, count, size = 'large', onClick, style, ...rest }) {
  const s = {
    background: 'none', border: 'none', fontFamily: 'var(--font-default)',
    fontSize: 'inherit', lineHeight: 'inherit', fontWeight: 600,
    padding: size === 'small' ? '8px 0' : '12px 0',
    color: selected ? 'var(--color-text-default)' : 'var(--color-text-light)',
    boxShadow: selected ? 'var(--color-text-default) 0 -2px 0 inset' : 'transparent 0 -2px 0 inset',
    cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.5 : 1,
    display: 'flex', alignItems: 'center', gap: '6px',
    transition: 'color 100ms, box-shadow 100ms', ...style,
  };
  const countS = { fontFamily: 'var(--font-mono)', fontSize: '12px', fontWeight: 500, padding: '0 5px', background: 'var(--color-background-gray)', borderRadius: '4px', color: 'var(--color-text-default)' };
  return React.createElement('button', { role: 'tab', type: 'button', 'aria-selected': selected, disabled, onClick, style: s, ...rest },
    children,
    count !== undefined && React.createElement('span', { style: countS }, count)
  );
}
