import { Button, ButtonProps } from "@patternfly/react-core";

export interface BusyButtonProps extends ButtonProps {
  readonly isBusy: boolean;
}

export const BusyButton = (props: BusyButtonProps) => {
  const { isBusy, children } = props;
  const { isBusy: _, ...baseProps } = props;
  return (
    <>
      {isBusy && (
        <Button {...baseProps} icon={undefined} isLoading={isBusy}>
          {children}
        </Button>
      )}
      {!isBusy && <Button {...baseProps}>{children}</Button>}
    </>
  );
};
