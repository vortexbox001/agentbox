export function Checkbox({ checked, onChange, label, disabled, style, ...rest }) {
  const wrapS = { display: 'flex', alignItems: 'center', gap: '8px', cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.5 : 1, ...style };
  const boxS = {
    width: '16px', height: '16px', borderRadius: '4px', flexShrink: 0,
    border: checked ? 'none' : '2px solid var(--color-checkbox-unchecked)',
    backgroundColor: checked ? 'var(--color-checkbox-checked)' : 'transparent',
    display: 'flex', alignItems: 'center', justifyContent: 'center', transition: 'all 150ms',
  };
  const checkmark = checked ? React.createElement('svg', { width: 10, height: 10, viewBox: '0 0 24 24', fill: 'none', stroke: '#fff', strokeWidth: 3, strokeLinecap: 'round', strokeLinejoin: 'round' },
    React.createElement('path', { d: 'M20 6L9 17l-5-5' })
  ) : null;
  return React.createElement('label', { style: wrapS, ...rest },
    React.createElement('span', { style: boxS }, checkmark),
    label && React.createElement('span', { style: { font: 'var(--type-body-md)', color: 'var(--color-text-default)' } }, label),
    React.createElement('input', { type: 'checkbox', checked, onChange: e => onChange && onChange(e.target.checked), disabled, style: { display: 'none' } })
  );
}
