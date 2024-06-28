import {
  Dropdown,
  DropdownToggle,
  Flex,
  FlexItem,
} from "@patternfly/react-core";
import { ReactNode, useCallback, useState } from "react";
import { useBreakpoint } from "@ansible/ansible-ui-framework";

interface PageMastheadDropdownProps {
  readonly id: string;
  readonly icon: ReactNode;
  readonly userName: string;
  readonly children: ReactNode;
}

export function PageMastheadDropdown(props: PageMastheadDropdownProps) {
  const isSmallOrLarger = useBreakpoint("sm");
  const [open, setOpen] = useState(false);
  const { id, icon, userName, children } = props;
  const onSelect = useCallback(() => setOpen((open) => !open), []);
  const onToggle = useCallback(() => setOpen((open) => !open), []);
  const _children = Array.isArray(children) ? children : [children];

  return (
    <Dropdown
      id={id}
      onSelect={onSelect}
      toggle={
        <DropdownToggle
          toggleIndicator={null}
          onToggle={onToggle}
          data-testid="page-masthead-dropdown__button"
        >
          <Flex
            alignItems={{ default: "alignItemsCenter" }}
            flexWrap={{ default: "nowrap" }}
            spaceItems={{ default: "spaceItemsSm" }}
          >
            <FlexItem>{icon}</FlexItem>
            {isSmallOrLarger && <FlexItem wrap="nowrap">{userName}</FlexItem>}
          </Flex>
        </DropdownToggle>
      }
      isOpen={open}
      isPlain
      dropdownItems={_children}
      position="right"
      data-cy={id}
      data-testid="page-masthead-dropdown"
    />
  );
}
