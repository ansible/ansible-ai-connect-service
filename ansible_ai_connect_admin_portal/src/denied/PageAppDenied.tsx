import {
  PageFramework,
  PageLayout,
  PageNavigationItem,
} from "@ansible/ansible-ui-framework";
import { Page } from "@patternfly/react-core";
import { ReactNode, useMemo } from "react";
import { PageSidebar } from "../PageSidebar";
import "../PageApp.css";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { PageDenied } from "./PageDenied";

interface PageAppDeniedProps {
  readonly header: ReactNode;
  readonly navigationItems: PageNavigationItem[];
  readonly hasSubscription: boolean;
}

/**
 * This is in essence a bit of hackery just to show the sidebar.
 * All navigation items have no operation and the only content
 * to be shown is <PageDenied />.
 * @param props
 * @constructor
 */
export function PageAppDenied(props: PageAppDeniedProps) {
  const { navigationItems, header, hasSubscription } = props;
  const navigationItemsWithRoot = useMemo<PageNavigationItem[]>(
    () => [
      {
        path: "*",
        element: (
          <PageRouterLayout
            header={header}
            navigationItems={navigationItems}
            hasSubscription={hasSubscription}
          />
        ),
        children: navigationItems,
      },
    ],
    [header, navigationItems, hasSubscription],
  );

  const router = useMemo(
    () => createBrowserRouter(navigationItemsWithRoot),
    [navigationItemsWithRoot],
  );

  return <RouterProvider router={router} />;
}

function PageRouterLayout(props: PageAppDeniedProps) {
  const { header, navigationItems, hasSubscription } = props;
  return (
    <PageFramework>
      <Page
        header={header}
        sidebar={<PageSidebar navigation={navigationItems} />}
      >
        <PageLayout>
          {hasSubscription && (
            <PageDenied
              titleKey={"NoPermissionsTitle"}
              captionKey={"NoPermissionsContactOrgCaption"}
            />
          )}
          {!hasSubscription && (
            <PageDenied
              titleKey={"NoPermissionsNoSubscriptionTitle"}
              captionKey={"NoPermissionsNoSubscriptionContactOrgCaption"}
            />
          )}
        </PageLayout>
      </Page>
    </PageFramework>
  );
}
