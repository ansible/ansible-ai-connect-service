import React, { useState } from "react";
import { Switch } from "@patternfly/react-core";

export const ColorThemeSwitch = () => {
  const [isChecked, setIsChecked] = useState<boolean>(false);
  const handleChange = (
    _event: React.FormEvent<HTMLInputElement>,
    checked: boolean,
  ) => {
    setIsChecked(checked);
    const element = document.getElementsByTagName("html");
    element[0].classList.remove(
      checked ? "pf-v6-theme-light" : "pf-v6-theme-dark",
    );
    element[0].classList.add(
      checked ? "pf-v6-theme-dark" : "pf-v6-theme-light",
    );
  };

  return (
    <Switch
      id="color-theme-switch"
      label="Dark Mode"
      isChecked={isChecked}
      onChange={handleChange}
      ouiaId="ColorThemeSwitch"
    />
  );
};
