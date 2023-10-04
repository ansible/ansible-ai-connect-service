import { Dropdown, DropdownToggle, Flex, FlexItem } from '@patternfly/react-core';
import { ReactNode, useCallback, useState } from 'react';
import {useBreakpoint} from "@ansible/ansible-ui-framework";

export function PageMastheadDropdown(props: {
  id: string;
  icon: ReactNode;
  label?: string;
  children: ReactNode;
}) {
  const isSmallOrLarger = useBreakpoint('sm');
  const [open, setOpen] = useState(false);
  const onSelect = useCallback(() => setOpen((open) => !open), []);
  const onToggle = useCallback(() => setOpen((open) => !open), []);
  const children = Array.isArray(props.children) ? props.children : [props.children];

  return (
    <Dropdown
      id={props.id}
      onSelect={onSelect}
      data-testid="page-masthead-dropdown"
      toggle={
        <DropdownToggle
            toggleIndicator={null} onToggle={onToggle}
            data-testid="page-masthead-dropdown__button"
        >
          <Flex
            alignItems={{ default: 'alignItemsCenter' }}
            flexWrap={{ default: 'nowrap' }}
            spaceItems={{ default: 'spaceItemsSm' }}
          >
            <FlexItem>{props.icon}</FlexItem>
            {isSmallOrLarger && <FlexItem wrap="nowrap">{props.label}</FlexItem>}
          </Flex>
        </DropdownToggle>
      }
      isOpen={open}
      isPlain
      dropdownItems={children}
      position="right"
      data-cy={props.id}
    />
  );
}
