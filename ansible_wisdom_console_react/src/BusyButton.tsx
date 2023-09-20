import {Button, ButtonProps} from "@patternfly/react-core";

export interface BusyButtonProps extends ButtonProps {
    isBusy: boolean;

}

export const BusyButton = (props: BusyButtonProps) => {
    const {isBusy, children} = props;
    return (
        <>
            {isBusy && (
                <Button
                    {...props}
                    icon={undefined}
                    isLoading={isBusy}>
                    {children}
                </Button>
            )}
            {!isBusy && (
                <Button {...props}>
                    {children}
                </Button>
            )}
        </>
    )
}
