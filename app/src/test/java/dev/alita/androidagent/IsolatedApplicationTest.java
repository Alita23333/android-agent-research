package dev.alita.androidagent;

import android.app.Application;
import android.os.Process;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.Config;
import org.robolectric.annotation.Implements;
import org.robolectric.annotation.Implementation;
import static org.junit.Assert.*;

@RunWith(RobolectricTestRunner.class)
@Config(application = Application.class, sdk = 35, shadows = IsolatedApplicationTest.IsolatedProcess.class)
public class IsolatedApplicationTest {
    @Implements(Process.class)
    public static class IsolatedProcess extends org.robolectric.shadows.ShadowProcess {
        @Implementation public static boolean isIsolated() { return true; }
    }
    @Test public void isolatedApplicationReturnsBeforeAnyOwnerContextAccess() {
        // No base Context attached: accessing files/settings/database would fail this test.
        AgentApplication app = new AgentApplication();
        app.onCreate();
        try { app.getGraph(); fail("isolated process initialized owner graph"); }
        catch (kotlin.UninitializedPropertyAccessException expected) { assertTrue(expected.getMessage().contains("graph")); }
    }
}
