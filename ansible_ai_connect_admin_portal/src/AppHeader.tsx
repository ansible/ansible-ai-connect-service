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
import { readCookie } from "./api/api";

export interface AppHeaderProps {
  readonly userName: string;
}

export function AppHeader(props: AppHeaderProps) {
  const { t } = useTranslation();
  const { userName } = props;

  const handleLogout = () => {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/logout/";

    const csrfInput = document.createElement("input");
    csrfInput.type = "hidden";
    csrfInput.name = "csrfmiddlewaretoken";
    csrfInput.value = readCookie("csrftoken") || "";
    form.appendChild(csrfInput);

    document.body.appendChild(form);
    form.submit();
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
              onClick={handleLogout}
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
