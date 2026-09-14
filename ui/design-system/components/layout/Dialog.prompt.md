Dialog is a modal with blurred backdrop.
```jsx
<Dialog open={isOpen} onClose={() => setOpen(false)} title="Create Agent" subtitle="Set up a new agent runner">
  <TextInput label="Name" />
  <Button intent="primary">Create</Button>
</Dialog>
```
