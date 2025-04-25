import React, { useEffect } from "react";
import MessageBox from "@patternfly/chatbot/dist/dynamic/MessageBox";
import { TooltipProps } from "@patternfly/react-core";

// Define a reusable tooltip props object that can be used throughout the app
export const bodyAppendToTooltipProps: Partial<TooltipProps> = {
  appendTo: () => document.body,
  position: "auto",
  enableFlip: true,
  zIndex: 1000,
};

// CustomMessageBox using TooltipProps from @patternfly/react-core
interface CustomMessageBoxProps {
  children?: React.ReactNode;
  tooltipProps?: Partial<TooltipProps>;
}

// Wrapper for MessageBox that'll modify the appendTo behavior for JumpButton and feedback buttons
const CustomMessageBox: React.FC<CustomMessageBoxProps> = ({
  children,
  tooltipProps,
}) => {
  useEffect(() => {
    const originalMessageBox = MessageBox as any;
    if (originalMessageBox.defaultProps) {
      originalMessageBox.defaultProps.tooltipProps = {
        ...originalMessageBox.defaultProps.tooltipProps,
        ...(tooltipProps || {}),
        appendTo: tooltipProps?.appendTo || (() => document.body),
      };
    }

    return () => {
      // Reset the defaultProps
      if (
        originalMessageBox.defaultProps &&
        originalMessageBox.defaultProps.tooltipProps
      ) {
        delete originalMessageBox.defaultProps.tooltipProps.appendTo;
      }
    };
  }, [tooltipProps]);

  // Note: MessageBox doesn't directly accept tooltipProps, but patching its behavior in useEffect
  return <MessageBox>{children}</MessageBox>;
};

export default CustomMessageBox;
