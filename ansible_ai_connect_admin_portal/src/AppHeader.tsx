import { PageMasthead } from "@ansible/ansible-ui-framework";
import { useTranslation } from "react-i18next";
import {
  Brand,
  DropdownItem,
  ToolbarGroup,
  ToolbarItem,
} from "@patternfly/react-core";
import { UserCircleIcon } from "@patternfly/react-icons";
import { PageMastheadDropdown } from "./PageMastheadDropdown";
import RedHatLogo from "./redhat-logo.svg";

export interface AppHeaderProps {
  readonly userName: string;
}

export function AppHeader(props: AppHeaderProps) {
  const { t } = useTranslation();
  const { userName } = props;

  const logout = () => {
    window.location.assign("/logout");
  };

  return (
    <PageMasthead
      brand={
        <Brand alt="" widths={{ default: "125px", md: "125px" }}>
          <source media="(min-width: 125px)" srcSet={RedHatLogo} />
        </Brand>
      }
    >
      <ToolbarItem style={{ flexGrow: 1 }} />
      <ToolbarGroup variant="icon-button-group">
        <ToolbarItem>
          <PageMastheadDropdown
            id="account-menu"
            icon={<UserCircleIcon />}
            userName={userName}
          >
            <DropdownItem
              id="logout"
              label={t("Logout")}
              onClick={logout}
              data-testid="app-header__logout"
            >
              {t("Logout")}
            </DropdownItem>
          </PageMastheadDropdown>
        </ToolbarItem>
      </ToolbarGroup>
    </PageMasthead>
  );
}
