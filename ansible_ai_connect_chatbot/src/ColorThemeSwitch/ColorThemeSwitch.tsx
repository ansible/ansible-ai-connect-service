import React, { useState } from "react";
import { Switch } from "@patternfly/react-core";

export const ColorThemeSwitch = () => {
  const [isChecked, setIsChecked] = useState<boolean>(false);
  const handleChange = (
    _event: React.FormEvent<HTMLInputElement>,
    checked: boolean,
  ) => {
    setIsChecked(checked);
    const htmlElementClassList =
      document.getElementsByTagName("html")[0].classList;
    if (checked) {
      htmlElementClassList.add("pf-v6-theme-dark");
    } else {
      htmlElementClassList.remove("pf-v6-theme-dark");
    }
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
