import {
  Dropdown,
  MenuToggle,
  MenuToggleElement,
  Flex,
  FlexItem,
  DropdownList,
  DropdownItem,
} from "@patternfly/react-core";
import React from "react";
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
  const [isOpen] = React.useState(false);

  return (
    <Dropdown
      id={id}
      onSelect={onSelect}
      toggle={(toggleRef: React.Ref<MenuToggleElement>) => (
        <MenuToggle
          ref={toggleRef}
          onClick={onToggle}
          isExpanded={isOpen}
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
        </MenuToggle>
      )}
      isOpen={open}
      isPlain
      data-cy={id}
      data-testid="page-masthead-dropdown__button"
    >
      <DropdownList>
        <DropdownItem>{_children}</DropdownItem>
      </DropdownList>
    </Dropdown>
  );
}
