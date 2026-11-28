import "@tanstack/react-table";

declare module "@tanstack/react-table" {
  // Column metadata understood by the shared table styles.
  interface ColumnMeta<_TData, _TValue> {
    align?: "right";
  }
}
